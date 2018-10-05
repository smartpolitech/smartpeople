#
# Copyright (C) 2018 by YOUR NAME HERE
#
#    This file is part of RoboComp
#
#    RoboComp is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    RoboComp is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with RoboComp.  If not, see <http://www.gnu.org/licenses/>.
#

import sys, os, traceback, time
import cv2
import numpy as np
import requests
import threading
import Queue
import itertools
from PySide import QtGui, QtCore
from genericworker import *


class SpecificWorker(GenericWorker):
	def __init__(self, proxy_map):
		super(SpecificWorker, self).__init__(proxy_map)


	def setParams(self, params):
		self.cameras = []
		try:
			for r in range(0, 100):
				camera = "Camera" + str(r)
				self.cameras.append(params[camera])
				print "Adding camera ", camera
		except:
			print "Cameras: "
			for c in self.cameras:
				print "\t ", c

		self.streams = []
		self.fgbgs = []
		for c in self.cameras:
			self.streams.append(requests.get(c, stream=True))
			self.fgbgs.append(cv2.createBackgroundSubtractorMOG2())

		self.timer.timeout.connect(self.compute)
		self.Period = 5
		self.timer.start(self.Period)

		self.imgs = [None] * len(self.cameras)
		self.diccionarioCamaras = {'camaras': []}
		return True

	def cameraThread(self, camera):
		kernel = np.ones((5, 5), np.uint8)
		imageNumber = 0;  # contador imagen
		while (True):
			time.sleep(0.05)
			# millis = int(round(time.time() * 1000))
			try:
				ret, frame = self.readImg(self.streams[camera])
				fgmask = self.fgbgs[camera].apply(frame)
				erode = cv2.erode(fgmask, kernel, iterations=2)
				dilate = cv2.dilate(erode, kernel, iterations=2)
				if cv2.countNonZero(dilate) > 100:
					f = open('camerasPeople/camera' + str(camera) + '/' + str(imageNumber) + '.txt', 'w')
					img = TImage(frame.shape[1], frame.shape[0], 3, frame.data)
					people = self.openposeserver_proxy.processImage(img)
					serialized_people = pickle.dumps(people)
					f.write(serialized_people)
					self.imgs[camera] = self.drawPose(people, frame)
					# ret, jpege = cv2.imencode('.jpg', img)
					cv2.imwrite("imagenes/camera" + str(camera) + "/" + "imageNumber" + str(imageNumber) + ".jpg",
					            frame);  # guardo imagen
					imageNumber = imageNumber + 1;  # contador imagen
					f.close()
				# millis2 = int(round(time.time() * 1000))
				# print "Leo con camara " + str(camera) + " " + str(millis2 - millis)
			except Ice.Exception, e:
				traceback.print_exc()
				print e
			# indicar de alguna manera que hemos escrito en imgs

	def initCameraThreads(self):  # para iniciar el hilo de cada camara y crear los diccionarios
		diccionarios = []
		# time.sleep(2)
		for c in range(len(self.cameras)):
			t = threading.Thread(target=self.cameraThread, args=(c,))
			diccionario = {'url': self.cameras[c], 'cameraThread': t, 'imagegrid': self.imgs}
			diccionarios.append(diccionario)
			t.start()

		for c in range(len(diccionarios)):
			self.diccionarioCamaras['camaras'].append(diccionarios[c])

	@QtCore.Slot()
	def compute(self):
		print 'SpecificWorker.compute...'
		#inicio = time.time()
		kernel = np.ones((5, 5), np.uint8)
		try:
			for c in range(len(self.cameras)):
					ret, frame = self.readImg(self.streams[c])
					fgmask = self.fgbgs[c].apply(frame)
					erode = cv2.erode(fgmask, kernel, iterations = 2)
					dilate = cv2.dilate(erode, kernel, iterations = 2)
					if cv2.countNonZero(dilate) > 100:
						self.imgs[c] = frame
						print "camera read"
		except Ice.Exception, e:
			traceback.print_exc()
			print e
		imggrid = self.drawGrid(3, 2, self.imgs)
		cv2.imshow('Grid', imggrid)
		return True

	def readImg(self, stream):
		bytes = ''
		for chunk in stream.iter_content(chunk_size=1024):
			bytes += chunk
			a = bytes.find(b'\xff\xd8')
			b = bytes.find(b'\xff\xd9')
			if a != -1 and b != -1:
				jpg = bytes[a:b+2]
				bytes = bytes[b+2:]
				if len(jpg) > 0:
					img = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
					return True, img


	def drawGrid(self, w, h, imgs):
		n = w*h
		for j in range(0,5):
			if any(i.shape != imgs[j].shape for i in imgs[1:]):
				raise ValueError('Not all images have the same shape.')
			img_h, img_w, img_c = imgs[j].shape
			m_x = 0
			m_y = 0
			imgmatrix = np.zeros((img_h * h + m_y * (h - 1),img_w * w + m_x * (w - 1),img_c),np.uint8)

			# imgmatrix.fill(255)
			positions = itertools.product(range(w), range(h))
			for (x_i, y_i), img in itertools.izip(positions, imgs):
				x = x_i * (img_w + m_x)
				y = y_i * (img_h + m_y)
				imgmatrix[y:y+img_h, x:x+img_w, :] = img

		return imgmatrix