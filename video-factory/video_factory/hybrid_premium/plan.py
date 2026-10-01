from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
VIDEO_EXTENSIONS={'.mp4','.mov','.mkv','.webm','.m4v','.ogv'}
STILL_EXTENSIONS={'.jpg','.jpeg','.png','.webp','.gif','.bmp'}
class PlanValidationError(ValueError): pass
@dataclass(frozen=True)
class Shot:
 source:str; in_seconds:float; duration:float; label:str; grade:str='neutral'; source_class:str='licensed_motion'; license_ref:str|None=None; crop_x:float|None=None; zoom_crop:float|None=None; reframe_pixels:float=0.0
 @classmethod
 def from_dict(cls,x:dict[str,Any]):
  return cls(str(x['source']),float(x.get('in',0)),float(x['duration']),str(x.get('label','shot')),str(x.get('grade','neutral')),str(x.get('source_class','licensed_motion')),x.get('license_ref'),float(x['crop_x']) if x.get('crop_x') is not None else None,float(x['zoom_crop']) if x.get('zoom_crop') is not None else None,float(x.get('reframe_pixels',0)))
@dataclass(frozen=True)
class EditPlan:
 path:Path; id:str; title:str; duration:float; width:int; height:int; fps:int; shots:tuple[Shot,...]; captions:str|None=None; narration:str|None=None; music:str|None=None; effects:tuple[dict[str,Any],...]=field(default_factory=tuple); quality:dict[str,Any]=field(default_factory=dict); metadata:dict[str,Any]=field(default_factory=dict)
 @property
 def base_dir(self): return self.path.parent
 def resolve(self,p:str): return (self.base_dir/p).resolve()
 @classmethod
 def load(cls,path):
  p=Path(path).resolve();d=json.loads(p.read_text(encoding='utf-8'));o=cls(p,str(d['id']),str(d.get('title',d['id'])),float(d['duration']),int(d.get('width',1080)),int(d.get('height',1920)),int(d.get('fps',30)),tuple(Shot.from_dict(x) for x in d['shots']),d.get('captions'),d.get('narration'),d.get('music'),tuple(d.get('effects',[])),dict(d.get('quality',{})),dict(d.get('metadata',{})));o.validate();return o
 def validate(self,require_files=True):
  e=[]; lo,hi=self.quality.get('shot_duration_seconds',[.3,4]); b0,b1=self.quality.get('visual_beats',[1,999]); total=sum(s.duration for s in self.shots)
  if (self.width,self.height)!=(1080,1920):e.append('Hybrid Premium master must be 1080x1920')
  if not b0<=len(self.shots)<=b1:e.append('visual beat count outside target')
  for i,s in enumerate(self.shots,1):
   ext=Path(s.source).suffix.lower()
   if ext in STILL_EXTENSIONS:e.append(f'shot {i} uses a still image as motion')
   if ext not in VIDEO_EXTENSIONS:e.append(f'shot {i} unsupported video extension')
   if not lo<=s.duration<=hi:e.append(f'shot {i} duration outside range')
   if not s.license_ref:e.append(f'shot {i} missing license_ref')
   if require_files and not self.resolve(s.source).is_file():e.append(f'shot {i} source missing')
  if abs(total-self.duration)>max(.02,1/self.fps):e.append('shot durations do not equal master duration')
  if len({s.source for s in self.shots})<int(self.quality.get('minimum_unique_motion_sources',1)):e.append('not enough unique motion sources')
  for name,p in [('captions',self.captions),('narration',self.narration),('music',self.music)]:
   if p and require_files and not self.resolve(p).is_file():e.append(f'{name} missing')
  if e:raise PlanValidationError('Hybrid Premium plan rejected:\n- '+'\n- '.join(e))
