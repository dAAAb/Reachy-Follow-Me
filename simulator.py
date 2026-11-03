"""Official Reachy Mini MuJoCo assets + analytical IK. Never contacts a daemon/robot.
Actuator IDs are resolved by NAME: SDK comments/order differ between versions.
API uses anatomical left/right and degrees. MuJoCo antenna signs follow SDK backend.
"""
import io,math,time,threading
from importlib.resources import files
import numpy as np
import mujoco
from PIL import Image
import reachy_mini
from reachy_mini.kinematics.analytical_kinematics import AnalyticalKinematics
from reachy_mini.utils import create_head_pose
class Simulator:
 def __init__(self):
  self.lock=threading.Lock();self.latest={'yaw':0.,'left':0.,'right':0.};self.last=time.monotonic();self.active=False;self.image=b'';self.running=False;self.error=None
 def target(self,data):
  a=data['angles'];bounds={'yaw':(-35,35),'left':(0,70),'right':(0,70)}
  if set(a)!=set(bounds) or type(data['active']) is not bool:raise ValueError('fields')
  for k,(lo,hi) in bounds.items():
   if isinstance(a[k],bool) or not isinstance(a[k],(int,float)) or not math.isfinite(a[k]) or not lo<=a[k]<=hi:raise ValueError('angle')
  with self.lock:self.latest={k:float(v) for k,v in a.items()};self.active=data['active'];self.last=time.monotonic()
 def start(self):
  self.running=True;self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
 def close(self):
  self.running=False;self.thread.join(timeout=5)
 def frame(self):
  with self.lock:return self.image
 def loop(self):
  renderer=None
  try:
   model=mujoco.MjModel.from_xml_path(str(files(reachy_mini).joinpath('descriptions/reachy_mini/mjcf/scenes/empty.xml')));model.opt.timestep=.002
   data=mujoco.MjData(model);ik=AnalyticalKinematics(automatic_body_yaw=False)
   names=['yaw_body']+[f'stewart_{i}' for i in range(1,7)]
   ids={n:mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_ACTUATOR,n) for n in names+['left_antenna','right_antenna']}
   if min(ids.values())<0:raise RuntimeError('SDK actuator names changed')
   neutral=ik.ik(create_head_pose(yaw=0,degrees=True));target=data.ctrl.copy()
   for n,q in zip(names,neutral):target[ids[n]]=q
   # Starting pose: open-chain joints plus closed-loop rods settle through simulation.
   for n,i in ids.items():
    joint=model.actuator_trnid[i,0];data.qpos[model.jnt_qposadr[joint]]=target[i]
   data.ctrl[:]=target;mujoco.mj_forward(model,data)
   for _ in range(600):mujoco.mj_step(model,data)
   renderer=mujoco.Renderer(model,height=480,width=640);camera=mujoco.MjvCamera();camera.distance=.57;camera.azimuth=165;camera.elevation=-8;camera.lookat[:]=[0,0,.17]
   applied={'yaw':0.,'left':0.,'right':0.};last=time.monotonic()
   while self.running:
    start=time.monotonic();dt=min(.05,start-last);last=start
    with self.lock:desired=dict(self.latest);active=self.active and start-self.last<.5
    if active:
     for k in applied:applied[k]+=max(-100*dt,min(100*dt,desired[k]-applied[k]))
    q=ik.ik(create_head_pose(yaw=applied['yaw'],degrees=True))
    if np.isfinite(q).all():
     for n,v in zip(names,q):target[ids[n]]=v
    # Teaching 0 = lowered outward, 70 = raised upright. Opposite hinges need opposite signs.
    target[ids['left_antenna']]=-math.radians(70-applied['left'])
    target[ids['right_antenna']]=math.radians(70-applied['right'])
    data.ctrl[:]=target
    for _ in range(20):mujoco.mj_step(model,data)
    renderer.update_scene(data,camera=camera);pixels=renderer.render();buf=io.BytesIO();Image.fromarray(pixels).save(buf,format='JPEG',quality=85)
    with self.lock:self.image=buf.getvalue()
    time.sleep(max(0,.04-(time.monotonic()-start)))
  except Exception as e:
   self.error=repr(e);print('Simulator error:',type(e).__name__,str(e),flush=True)
  finally:
   if renderer:renderer.close()
