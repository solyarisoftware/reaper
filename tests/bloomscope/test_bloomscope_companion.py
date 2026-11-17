"""Exercise the actual Lua action against a small host-API stub, not a port."""
from pathlib import Path
import shutil
import subprocess
import unittest

SRC = Path(__file__).resolve().parents[2] / 'bloomscope'
STUB = r'''
local memory = {}
local project, track = {}, {}
local active, valid, enabled, offline = project, true, true, false
local rate, playrate, repeat_state, now = '48000', 1, 1, 100
local token, selected, count, guid, name = 0, 1, 1, 'fx-guid', 'Loop companion token'
local callback, exit_callback, messages, options
reaper = {
  set_action_options=function(v) options=v end,
  EnumProjects=function() return active end,
  GetSelectedTrack=function() return track end,
  CountSelectedTracks=function() return selected end,
  TrackFX_GetCount=function() return count end,
  TrackFX_GetParamName=function() return true,name end,
  TrackFX_GetFXGUID=function() return guid end,
  gmem_attach=function() end,
  gmem_read=function(i) return memory[i] or 0 end,
  gmem_write=function(i,v) memory[i]=v end,
  time_precise=function() return now end,
  TrackFX_GetParam=function() return token end,
  TrackFX_SetParam=function(_,_,_,v) token=v end,
  ValidatePtr2=function() return valid end,
  GetSet_LoopTimeRange2=function() return 0, 3 end,
  GetAudioDeviceInfo=function() return true,rate end,
  GetSetRepeatEx=function() return repeat_state end,
  Master_GetPlayRate=function() return playrate end,
  Master_GetPlayRateAtTime=function() return playrate end,
  GetPlayPositionEx=function() return 0 end,
  TrackFX_GetEnabled=function() return enabled end,
  TrackFX_GetOffline=function() return offline end,
  TimeMap2_timeToQN=function(_,t) return 2*t end,
  atexit=function(f) exit_callback=f end,
  defer=function(f) callback=f end,
  ShowMessageBox=function() messages=(messages or 0)+1 end,
}
local function start() assert(loadfile(SOURCE))() end
local function pump()
  local f=callback; callback=nil
  if f then f() else error('no deferred callback') end
end
local function handshake()
  start()
  assert(token>0)
  local b=(token%64)*32
  memory[b+16]=12345
  pump()
  assert(memory[b+2]==12345 and memory[b+3]==1)
  assert(memory[b]%2==0)
  return b
end
'''


@unittest.skipUnless(shutil.which('lua5.4'), 'lua5.4 is required for actual-action tests')
class CompanionTests(unittest.TestCase):
    def run_lua(self, body):
        source = str(SRC / 'bloomscope_loop_companion.lua')
        program = f'local SOURCE = [[{source}]]\n' + STUB + body
        result = subprocess.run(['lua5.4', '-'], input=program, text=True,
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handshake_and_even_publication(self):
        self.run_lua('local b=handshake(); assert(memory[b+4]==0 and memory[b+5]==3); assert(options==1)')

    def test_duplicate_action_copy_does_not_start_second_loop(self):
        self.run_lua('local b=handshake(); local old=callback; start(); assert(callback==old)')

    def test_tab_switch_suspends_then_resumes(self):
        self.run_lua('local b=handshake(); active={}; pump(); assert(memory[b+3]==0); '
                     'active=project; pump(); assert(memory[b+3]==1)')

    def test_offline_and_bypass_suspend(self):
        self.run_lua('local b=handshake(); offline=true; pump(); assert(memory[b+3]==0); '
                     'offline=false; enabled=false; pump(); assert(memory[b+3]==0)')

    def test_nonunit_playrate_and_repeat_off_suspend(self):
        self.run_lua('local b=handshake(); playrate=0.5; pump(); assert(memory[b+3]==0); '
                     'playrate=1; repeat_state=0; pump(); assert(memory[b+3]==0)')

    def test_invalid_audio_rate_suspends_without_throwing(self):
        self.run_lua("local b=handshake(); rate=''; pump(); assert(memory[b+3]==0)")

    def test_nonce_change_stops_and_invalidates_context(self):
        self.run_lua('local b=handshake(); memory[b+16]=67890; pump(); assert(callback==nil); '
                     'exit_callback(); assert(memory[b+3]==0)')

    def test_deleted_fx_and_token_change_stop(self):
        for condition in ('valid=false', 'count=0', 'token=token+1'):
            with self.subTest(condition=condition):
                self.run_lua(f'local b=handshake(); {condition}; pump(); '
                             'assert(callback==nil); exit_callback(); assert(memory[b+3]==0)')

    def test_stolen_slot_is_not_overwritten_by_exit(self):
        self.run_lua('local b=handshake(); memory[b+1]=999; memory[b+3]=7; pump(); '
                     'assert(callback==nil); exit_callback(); assert(memory[b+3]==7)')

    def test_ambiguous_track_and_absent_fx_are_rejected(self):
        for condition in ('selected=0', 'count=0', "name='other'", 'count=2'):
            with self.subTest(condition=condition):
                self.run_lua(f'{condition}; start(); assert(messages==1 and callback==nil and token==0)')

    def test_missing_handshake_times_out(self):
        self.run_lua('start(); now=106; pump(); assert(callback==nil); exit_callback()')

    def test_active_slots_are_not_reused(self):
        self.run_lua('for slot=0,63 do memory[slot*32+1]=999; memory[slot*32+10]=now end; '
                     'start(); assert(messages==1 and token==0 and callback==nil)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
