-- Native acceptance runner: only an explicitly named empty disposable project.
-- Requires the already-installed js_ReaScriptAPI extension; never installs it.
-- Copy to a temporary work directory containing expected-project.txt and
-- expected-resource.txt, with Windows paths. Test copies must be under
-- <resource>/Effects/CCScopeAcceptance23, built by ccscope_acceptance_probe.py.
local dir = debug.getinfo(1, 'S').source:gsub('^@', ''):match('^(.*[\\/])')
local function read(name)
  local f = assert(io.open(dir .. name, 'r')); local s = f:read('*a'); f:close()
  return s:gsub('%s+$', '')
end
local function norm(s) return s:gsub('\\', '/'):lower() end
local expected = read('expected-project.txt')
local testproj, filename = reaper.EnumProjects(-1, '')
assert(norm(filename) == norm(expected) and reaper.CountTracks(testproj) == 0, 'Not the designated empty project')
assert(norm(reaper.GetResourcePath()) == norm(read('expected-resource.txt')), 'Unexpected resource directory')
assert(reaper.APIExists('JS_WindowMessage_Send') and reaper.APIExists('JS_Window_Resize'), 'js_ReaScriptAPI required')
assert(reaper.EnumProjects(1, '') == nil, 'Other project tabs are open')
reaper.gmem_attach('CCScopeAcceptance23')
local mode_file = io.open(dir .. 'mode.txt', 'r')
local ui_only = mode_file and mode_file:read('*a'):match('ui') ~= nil
if mode_file then mode_file:close() end
local suffix = ui_only and '-ui' or ''
local run_id = string.format('%.6f',reaper.time_precise())
local function write_status(status)
  local f=assert(io.open(dir..'status'..suffix..'.txt','w'))
  f:write(status..'\nrun_id='..run_id..'\n'); f:close()
end
write_status('RUNNING')
local log = assert(io.open(dir .. 'acceptance' .. suffix .. '.log', 'w'))
local frames = assert(io.open(dir .. 'frames' .. suffix .. '.csv', 'w'))
local blocks = assert(io.open(dir .. 'blocks' .. suffix .. '.csv', 'w'))
frames:write('scenario,variant,draw_ms,interval_ms,width,height\n')
blocks:write('scenario,variant,block_us\n')
local track, fx, root, canvas
local original_mouse_x, original_mouse_y
local held_left, held_right = false, false
local function native_input(action, delta)
  local address = root and reaper.JS_Window_AddressFromHandle(root) or 0
  local command = string.format('"%sui_input.exe" %.0f %s %d',dir,address,action,delta or 0)
  -- A timeout has uncertain injection state; an explicit nonzero exit has none.
  if action=='left-down' then held_left=true end
  if action=='right-down' then held_right=true end
  local result = reaper.ExecProcess(command,2000)
  local code = result and tonumber(result:match('^(%d+)'))
  if code and code~=0 then
    if action=='left-down' then held_left=false end
    if action=='right-down' then held_right=false end
  end
  assert(code==0,'Input helper refused action: '..action..' ('..tostring(result)..')')
  if action=='left-up' then held_left=false end
  if action=='right-up' then held_right=false end
end
local function release_test_input()
  if held_left then pcall(native_input,'left-up'); held_left=false end
  if held_right then pcall(native_input,'right-up'); held_right=false end
  if original_mouse_x then
    reaper.JS_Mouse_SetPosition(original_mouse_x,original_mouse_y)
    original_mouse_x,original_mouse_y=nil,nil
  end
end
-- Also runs on manual ReaScript termination; never save projects or quit here.
reaper.atexit(release_test_input)
local function say(s) log:write(s .. '\n'); log:flush() end
local function g(i) return reaper.gmem_read(i) end
local function wait(seconds)
  local until_time = reaper.time_precise() + seconds
  repeat coroutine.yield() until reaper.time_precise() >= until_time
end
local function await(fn, message, seconds)
  local until_time = reaper.time_precise() + (seconds or 3)
  repeat
    if fn() then return end
    assert(reaper.time_precise() < until_time, message)
    coroutine.yield()
  until false
end
local function identify_canvas()
  root = assert(reaper.TrackFX_GetFloatingWindow(track, fx), 'No floating FX window')
  local _, list = reaper.JS_Window_ListAllChild(root)
  local candidates = {root}
  for hex in list:gmatch('[^,]+') do
    candidates[#candidates+1] = reaper.JS_Window_HandleFromAddress(tonumber(hex:gsub('^0x',''),16))
  end
  local best, score = nil, math.huge
  for _, hwnd in ipairs(candidates) do
    local ok, w, h = reaper.JS_Window_GetClientSize(hwnd)
    if ok then
      local d = math.abs(w-g(10)) + math.abs(h-g(11))
      if d < score then best, score = hwnd, d end
    end
  end
  assert(best and score == 0, 'Could not identify the exact JSFX canvas')
  canvas = best
end
local function resize(w, h)
  local ok, left, top, right, bottom = reaper.JS_Window_GetRect(root)
  assert(ok)
  local rw = right-left + w-g(10)
  local rh = bottom-top + h-g(11)
  assert(reaper.JS_Window_SetPosition(root, 20, 20, math.floor(rw), math.floor(rh)))
  await(function() return g(10)==w and g(11)==h end, 'Native canvas resize did not reach requested dimensions')
  wait(0.12)
  say(string.format('RESIZE PASS %dx%d cache=%d',g(10),g(11),g(15)))
end
local function setup(variant, cfg)
  reaper.gmem_write(2,0)
  if track then reaper.DeleteTrack(track) end
  for i=0, 8000 do reaper.gmem_write(i,0) end
  reaper.gmem_write(1,cfg.streams); reaper.gmem_write(3,cfg.seed)
  reaper.InsertTrackAtIndex(0,false); track = reaper.GetTrack(testproj,0)
  reaper.SetMediaTrackInfo_Value(track,'B_MAINSEND',0)
  reaper.SetMediaTrackInfo_Value(track,'I_MIDIHWOUT',-1)
  reaper.SetMediaTrackInfo_Value(track,'I_RECINPUT',-1)
  reaper.SetMediaTrackInfo_Value(track,'I_RECARM',1)
  reaper.SetMediaTrackInfo_Value(track,'I_RECMON',1)
  local gen = reaper.TrackFX_AddByName(track,'JS: CCScopeAcceptance23/generator.jsfx',false,-1)
  local input = reaper.TrackFX_AddByName(track,'JS: CCScopeAcceptance23/input.jsfx',false,-1)
  fx = reaper.TrackFX_AddByName(track,'JS: CCScopeAcceptance23/'..variant..'/ccscope.jsfx',false,-1)
  local monitor = reaper.TrackFX_AddByName(track,'JS: CCScopeAcceptance23/monitor.jsfx',false,-1)
  assert(gen>=0 and input>=0 and fx>=0 and monitor>=0,'Missing test FX')
  for _, index in ipairs({gen,input,fx,monitor}) do
    reaper.TrackFX_SetNamedConfigParm(track,index,'force_auto_bypass','0')
  end
  reaper.TrackFX_SetParam(track,fx,1,cfg.freeze or 0)
  reaper.TrackFX_SetParam(track,fx,2,cfg.win)
  reaper.TrackFX_Show(track,fx,3)
  reaper.gmem_write(2,1)
  await(function() return g(4)>1 and g(28)>0 end,'No native GUI/audio telemetry',8)
  identify_canvas(); resize(1000,720)
end
local function midi_check(label)
  reaper.gmem_write(2,0); wait(0.12)
  local sent, received = g(100),g(102)
  assert(sent>0 and sent==received,'MIDI count mismatch or no events')
  assert(g(101)==0 and g(103)==0,'MIDI capture overflow')
  for i=0,sent-1 do
    assert(g(10000+i*2)==g(100000+i*2),'MIDI sample offset changed')
    if g(10000+i*2+1)~=g(100000+i*2+1) then
      say(string.format('MIDI DIAGNOSTIC index=%d offset=%d expected=%d actual=%d',i,g(10000+i*2),g(10000+i*2+1),g(100000+i*2+1)))
      error('MIDI bytes/order changed')
    end
  end
  say(string.format('MIDI PASS %s events=%d (CC, note on/off, program change, pitch bend); input[1]=%d output[1]=%d',label,sent,g(10003),g(100003)))
end
local function collect(cfg, variant)
  setup(variant,cfg); wait(1.2)
  local last_gfx, last_block = g(4),g(5)
  local finish_at = reaper.time_precise()+2.3
  local ng,nb=0,0
  while reaper.time_precise()<finish_at do
    local newest_gfx,newest_block=g(4),g(5)
    assert(newest_gfx-last_gfx<=1024 and newest_block-last_block<=2048,'Telemetry overflow')
    for n=last_gfx+1,newest_gfx do
      local p=5000+(n%1024)*2
      frames:write(string.format('%s,%s,%.9f,%.9f,%d,%d\n',cfg.name,variant,g(p),g(p+1),g(10),g(11)))
      ng=ng+1
    end
    for n=last_block+1,newest_block do
      blocks:write(string.format('%s,%s,%.9f\n',cfg.name,variant,g(2000+n%2048))); nb=nb+1
    end
    last_gfx,last_block=newest_gfx,newest_block
    coroutine.yield()
  end
  assert(ng>20 and nb>100,'Insufficient timing records')
  midi_check(cfg.name..'/'..variant)
  say(string.format('TIMING PASS %s/%s gfx=%d blocks=%d rate=%d blocksize=%d',cfg.name,variant,ng,nb,g(27),g(28)))
  frames:flush(); blocks:flush()
end
local function move(x,y)
  reaper.JS_Window_SetForeground(root)
  local sx,sy=reaper.JS_Window_ClientToScreen(canvas,math.floor(x),math.floor(y))
  reaper.JS_Mouse_SetPosition(sx,sy)
  wait(0.08)
end
local function click(x,y,right)
  move(x,y)
  native_input(right and 'right-down' or 'left-down')
  wait(0.12)
  native_input(right and 'right-up' or 'left-up')
  wait(0.12)
end
local function cell(i,right) click(g(40+i),18,right) end
local function choose(i,row)
  cell(i); assert(g(13)==i,'Selector did not open')
  click(g(73)+10,g(74)+2+row*15+7)
  assert(g(13)==0,'Selector did not close')
end
local function wheel_cell(i,amount)
  local x,y=g(40+i),18
  move(x,y)
  native_input('wheel',amount)
  wait(0.15)
end
-- The bar's geometry, measured once per variant: the cell centres, the labels
-- tier, and the position, width, rows and scroll of each selector's open list.
-- Comparing two variants' files is how a refactor proves it changed nothing.
local function geometry(variant)
  setup(variant,{streams=20,seed=20,win=10}); wait(0.25)
  local out = assert(io.open(dir..'geometry-'..variant..'.txt','w'))
  local function put(name, value) out:write(string.format('%s=%.6f\n', name, value)) end
  put('canvas_w', g(10)); put('canvas_h', g(11))
  for i=1,7 do put('cell'..i..'_x', g(40+i)) end
  put('labels_tier', g(79)); put('metrics_tier', g(18))
  put('layout_side', g(16)); put('side_fallback', g(71))
  put('visible_bars', g(62)); put('metrics_x', g(60)); put('start_y', g(61))
  for i=1,5 do
    cell(i)
    assert(g(13)==i,'Selector did not open while measuring geometry')
    put('menu'..i..'_x', g(73)); put('menu'..i..'_y', g(74))
    put('menu'..i..'_w', g(78)); put('menu'..i..'_rows', g(76))
    put('menu'..i..'_scroll', g(75))
    click(10, g(11)-40)                    -- outside the list: it closes, nothing else reacts
    assert(g(13)==0,'Selector did not close while measuring geometry')
  end
  out:close()
  say('GEOMETRY '..variant..' canvas='..g(10)..'x'..g(11))
end
local function ui_test()
  setup('candidate',{streams=20,seed=20,win=10}); wait(0.25)
  local cookie=g(91)
  original_mouse_x,original_mouse_y=reaper.GetMousePosition()
  choose(1,1); assert(g(20)==1 and g(17)==1,'CC filter failed')
  choose(2,2); assert(g(25)==2 and g(17)==0,'Combined channel filter failed')
  cell(2,true); assert(g(25)==0 and g(17)==1,'Channel default reset failed')
  cell(1,true); assert(g(20)==0 and g(17)==20,'CC default reset failed')
  wheel_cell(3,120); assert(g(22)==11,'Time-window wheel step failed')
  cell(3,true); assert(g(22)==10,'Time-window default reset failed')
  choose(4,2); assert(g(24)==2,'Dots selection failed')
  choose(5,1); assert(g(26)==1 and g(16)==1,'Rows-beside selection failed')
  resize(640,500); assert(g(16)==0 and g(71)==1,'Narrow-layout fallback failed')
  resize(1000,720); assert(g(16)==1 and g(71)==0,'Wide-layout recovery failed')
  cell(6); assert(g(12)==1,'Freeze button failed')
  local count,writepos,endpoint,clock,received=g(7),g(8),g(72),g(6),g(102)
  wait(0.3)
  assert(g(7)==count and g(8)==writepos and g(72)==endpoint,'Frozen data/window changed')
  assert(g(6)>clock and g(102)>received,'Audio/MIDI stopped during Freeze')
  wheel_cell(3,120); assert(g(22)==11 and g(72)==endpoint,'Frozen window change failed')
  for _,size in ipairs({{1200,800},{640,500},{2048,500},{2049,500},{1000,720}}) do
    resize(size[1],size[2])
    assert(g(91)==cookie and g(72)==endpoint,'Resize reset the instance/frozen timestamp')
    if size[1]>2048 then assert(g(15)==0,'Oversize native canvas unexpectedly cached') end
  end
  cell(7); assert(g(7)==0 and g(17)==20 and g(23)==0,'Clear while frozen failed')
  cell(6); await(function() return g(12)==0 and g(7)>0 end,'Acquisition did not resume')
  move(g(60)+10,g(61)+4); wait(0.15)
  assert(g(70)==1,'Metric hover tooltip did not paint')
  say('UI PASS: native SendInput clicks, selectors, wheel/reset, filtering, fallback, Freeze/Clear, hover and real window resize')
  midi_check('native-ui')
end
local function embed_test()
  -- WAK bits are probed only on a new disposable track, never a user project.
  -- Native gfx_ext_flags bit 1, not a guessed chunk value, is the success oracle.
  reaper.TrackFX_Show(track,fx,2)
  reaper.SetMediaTrackInfo_Value(track,'I_HEIGHTOVERRIDE',600)
  reaper.TrackList_AdjustWindows(false)
  local ok,original=reaper.GetTrackStateChunk(track,'',false); assert(ok)
  local guid=reaper.TrackFX_GetFXGUID(track,fx)
  local pos=assert(original:find('FXID '..guid,1,true))
  local begin_at,end_at=original:find('WAK [^\r\n]+',pos)
  assert(begin_at and end_at,'Could not locate only the target FX WAK line')
  local passed=false
  for _,value in ipairs({'WAK 0 1','WAK 0 2','WAK 2 0','WAK 4 0','WAK 0 3'}) do
    local chunk=original:sub(1,begin_at-1)..value..original:sub(end_at+1)
    reaper.gmem_write(77,0)
    assert(reaper.SetTrackStateChunk(track,chunk,false))
    reaper.TrackList_AdjustWindows(false); wait(0.5)
    if math.floor(g(77))%2==1 then
      say(string.format('EMBED PASS: native gfx_ext_flags=%d canvas=%dx%d (%s)',g(77),g(10),g(11),value))
      passed=true; break
    end
  end
  assert(reaper.SetTrackStateChunk(track,original,false))
  say(passed and 'EMBED RESULT PASS' or 'EMBED RESULT NOT VERIFIED')
  return passed
end
local function finish(status)
  release_test_input()
  reaper.gmem_write(2,0)
  local current=reaper.EnumProjects(-1,'')
  if current==testproj then reaper.Main_OnCommand(1016,0) end
  if track and reaper.ValidatePtr(track,'MediaTrack*') then reaper.DeleteTrack(track) end
  reaper.Main_SaveProjectEx(testproj,expected,8)
  say(status)
  frames:close(); blocks:close(); log:close()
  write_status(status)
  if current==testproj and reaper.EnumProjects(1,'')==nil then
    reaper.defer(function() reaper.Main_OnCommand(40004,0) end)
  end
end
local co=coroutine.create(function()
  say('Native REAPER '..reaper.GetAppVersion()..'; js_ReaScriptAPI '..tostring(reaper.JS_ReaScriptAPI_Version()))
  reaper.Main_OnCommand(1007,0)
  local cases={
    {name='four-live',streams=4,seed=4,win=10},
    {name='many-live',streams=128,seed=128,win=10},
    {name='sparse-stale',streams=4,seed=128,win=1},
    {name='twenty-frozen',streams=20,seed=20,win=10,freeze=1},
  }
  if not ui_only then
    for _,cfg in ipairs(cases) do
      for _,variant in ipairs({'baseline','candidate'}) do collect(cfg,variant) end
    end
  end
  geometry('baseline'); geometry('candidate')
  ui_test(); return embed_test()
end)
local start=reaper.time_precise()
local function tick()
  if reaper.EnumProjects(-1,'')~=testproj then finish('STOP: current project changed'); return end
  if reaper.time_precise()-start>120 then finish('FAIL: overall timeout'); return end
  local ok,err=coroutine.resume(co)
  if not ok then finish('FAIL: '..tostring(err)); return end
  if coroutine.status(co)=='dead' then
    finish(err and 'PASS' or 'PASS WITH LIMITATION: embedded UI not verified'); return
  end
  reaper.defer(tick)
end
reaper.defer(tick)
