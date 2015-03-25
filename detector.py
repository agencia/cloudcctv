from __future__ import division

import io
import json
import time
import datetime
import picamera
import numpy as np
from subprocess import call
import Queue
import threading

motion_dtype = np.dtype([
    ('x', 'i1'),
    ('y', 'i1'),
    ('sad', 'u2'),
    ])

current_recording_time = 0
last_motion_time = 0
file_name = ''
detections = []
queue = Queue.Queue(0)

class Uploader(threading.Thread):
    def __init__(self,queue):
	threading.Thread.__init__(self)
	self.queue = queue

    def run(self):
	while True:
	    if self.queue.empty is not True :
	        load = self.queue.get()
	        self.upload(load)
	        self.queue.task_done()
	        print('task done')
	    else:
		print('empty')

    def upload(self,load):
	print('uploading')
	call(load)
	#self.queue.task_done()

class MyMotionDetector(object):
    def __init__(self, camera):
        width, height = camera.resolution
        self.cols = (width + 15) // 16
        self.cols += 1 # there's always an extra column
        self.rows = (height + 15) // 16

    def write(self, s):
	global last_motion_time
	global current_recording_time
	global file_name
	global detections
	global queue
        # Load the motion data from the string to a numpy array
        data = np.fromstring(s, dtype=motion_dtype)
        # Re-shape it and calculate the magnitude of each vector
        data = data.reshape((self.rows, self.cols))
        data = np.sqrt(
            np.square(data['x'].astype(np.float)) +
            np.square(data['y'].astype(np.float))
            ).clip(0, 255).astype(np.uint8)
        # If there're more than 50 vectors with a magnitude greater
        # than 60, then say we've detected motion
        if (data > 60).sum() > 50:
            print('Motion detected!')
	    if last_motion_time < current_recording_time :
		camera.capture('{0}jpg'.format(file_name), use_video_port=True)
		last_motion_time = current_recording_time
		detections.append({'title':'CDS I','date':datetime.datetime.fromtimestamp(int(current_recording_time)).strftime('%Y/%m/%d at %H:%M'),'description':'People from CDS I, Softtek','image':'{0}jpg'.format(file_name),'available':True,'video':'{0}mp4'.format(file_name)})
		if len(detections) > 20 :
		    detections.pop(0)
		with open('data.json', 'w') as outfile:
    		    json.dump(detections, outfile)
		queue.put(['aws','s3','rm','s3://cloudcctv/data.json'])
		queue.put(['aws','s3','mv','{0}jpg'.format(file_name),'s3://cloudcctv-thumbs'])
		queue.put(['aws','s3','cp','data.json','s3://cloudcctv'])
		#call(['aws','s3','mv','{0}jpg'.format(file_name),'s3://cloudcctv-thumbs'])
		#call(['aws','s3','mv','data.json','s3://cloudcctv'])
        # Pretend we wrote all the bytes of s
        return len(s)

with picamera.PiCamera() as camera:
    #stream = picamera.PiCameraCircularIO(camera, seconds=10)
    global last_motion_time
    global file_name
    global current_recording_time 
    global queue

    for i in range(1):
	t = Uploader(queue)
	t.deamon = True
	t.start()
    #1024,768
    camera.resolution = (320,240)
    camera.framerate = 15
    camera.start_recording(
        # Throw away the video data, but make sure we're using H.264
        '/dev/null', format='h264',
        # Record motion data to our custom output object
        motion_output=MyMotionDetector(camera)
        )
    current_recording_time = int(time.time())
    file_name = 'video{0}.'.format(current_recording_time)
    last_name = file_name
    camera.start_recording('{0}{1}'.format(file_name,'h264'), format='h264', splitter_port=2)
    #while True:
    try:
	while True:
            camera.wait_recording(10)
	    current_recording_time = int(time.time())
	    file_name = 'video{0}.'.format(current_recording_time)
	    camera.split_recording('{0}{1}'.format(file_name,'h264'), splitter_port=2)
	    queue.put(['MP4Box','-add','{0}{1}'.format(last_name,'h264'),'{0}{1}'.format(last_name,'mp4')])
	    queue.put(['rm', '{0}{1}'.format(last_name,'h264')])
	    queue.put(['aws','s3','mv', '{0}{1}'.format(last_name,'mp4'),'s3://cloudcctv-media'])
	    
	    last_name = file_name
            #write_video(stream)
    finally:
        camera.stop_recording()
	camera.stop_recording(splitter_port=2)


