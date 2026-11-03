"""Run with python -m unittest discover -s tests -p 'test_*.py'. No robot required."""
import json, math, os, tempfile, threading, time, unittest
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from reachy_follow_me.adapter import checked_target, sdk_antennas, mujoco_antennas, classroom_antennas
from reachy_follow_me.main import ReachyFollowMe

class AppTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.env=patch.dict(os.environ,{'REACHY_FOLLOW_ME_CACHE':self.temp.name});self.env.start()
  with patch.object(ReachyFollowMe,'_check_daemon_on_localhost',return_value=False):self.app=ReachyFollowMe()
  self.client=TestClient(self.app.settings_app,base_url='http://127.0.0.1:8043')
  self.headers={'origin':'http://127.0.0.1:8043'}
 def tearDown(self):self.client.close();self.env.stop();self.temp.cleanup()
 def test_package_ui_and_status(self):
  self.assertEqual(self.client.get('/').status_code,200)
  self.assertIn('base href="/static/"',self.client.get('/').text)
  self.assertEqual(self.client.get('/static/vision.js').status_code,200)
  self.assertFalse(self.client.get('/api/status').json()['armed'])
 def test_origin_host_and_limits(self):
  self.assertEqual(self.client.post('/api/enable',json={'confirmed':True}).status_code,403)
  self.assertEqual(self.client.get('/api/status',headers={'host':'attacker.example'}).status_code,403)
  self.assertEqual(self.client.post('/api/target',json={'angles':{'yaw':900,'left':0,'right':0},'active':True},headers=self.headers).status_code,400)
  self.assertEqual(self.client.post('/api/enable',json={'confirmed':True},headers=self.headers).status_code,409)
 def test_stop_and_no_automatic_rearm(self):
  self.app.ready=True;self.app.armed=True
  target={'angles':{'yaw':10,'left':70,'right':0},'active':True}
  self.assertEqual(self.client.post('/api/target',json=target,headers=self.headers).status_code,200)
  self.client.post('/api/stop',json={},headers=self.headers)
  self.assertFalse(self.app.armed)
  self.assertEqual(self.client.post('/api/target',json=target,headers=self.headers).status_code,409)
 def test_repeated_stop_does_not_resample_hold_target(self):
  self.app.has_control=True;self.app.armed=True
  self.app.disarm("stop");self.assertTrue(self.app.hold_requested)
  self.app.hold_requested=False # runtime captured the measured pose once
  self.app.disarm("inactive packet");self.assertFalse(self.app.hold_requested)
 def test_same_anatomical_mapping_in_sdk_and_mujoco(self):
  a={'yaw':0,'left':70,'right':0};sdk=sdk_antennas(a);sim=mujoco_antennas(a)
  self.assertAlmostEqual(sdk[0],math.radians(-70));self.assertEqual(sdk[1],0)
  self.assertEqual(sim['left_antenna'],0);self.assertAlmostEqual(sim['right_antenna'],math.radians(70))
  self.assertEqual(classroom_antennas(sdk),{'right':0,'left':70})
 def test_runtime_reads_without_moving_then_holds_on_timeout(self):
  class Robot:
   def __init__(self):self.calls=[];self.enabled=0
   def get_current_head_pose(self):return np.eye(4)
   def get_current_joint_positions(self):return [0]*7,[0,0]
   def enable_motors(self):self.enabled+=1
   def set_target(self,**kw):self.calls.append(kw)
  robot=Robot();stop=threading.Event();thread=threading.Thread(target=self.app.run,args=(robot,stop));thread.start()
  try:
   time.sleep(.09);self.assertFalse(robot.calls)
   self.client.post('/api/enable',json={'confirmed':True},headers=self.headers)
   time.sleep(.09);self.assertEqual(robot.enabled,1)
   self.client.post('/api/target',json={'angles':{'yaw':35,'left':0,'right':70},'active':True},headers=self.headers)
   time.sleep(.09);self.assertTrue(robot.calls)
   self.app.last_target=time.monotonic()-1;time.sleep(.09);self.assertFalse(self.app.armed)
  finally:stop.set();thread.join(2)

if __name__=='__main__':unittest.main()
