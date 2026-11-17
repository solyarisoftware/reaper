-- @noindex
-- Installed and registered by the BloomScope JSFX package, not a separate package.
-- BloomScope loop companion: explicit, one project and one FX instance.
-- Start with exactly one selected track containing exactly one BloomScope.
-- No startup hook. Re-launching this action stops it, without a dialog.
reaper.set_action_options(1)
local NS, SLOTS, STRIDE = 'BloomScope_Loop_v1', 64, 32
local function publish(base, fields)
  local seq = reaper.gmem_read(base)
  seq = math.floor(seq / 2) * 2 + 1
  reaper.gmem_write(base, seq)
  for i, value in ipairs(fields) do reaper.gmem_write(base + i, value) end
  reaper.gmem_write(base, seq + 1)
end

local project = reaper.EnumProjects(-1)
local track = reaper.GetSelectedTrack(project, 0)
if not track or reaper.CountSelectedTracks(project) ~= 1 then
  reaper.ShowMessageBox('Select exactly one track containing one BloomScope.', 'BloomScope', 0)
  return
end
local fx
for i = 0, reaper.TrackFX_GetCount(track) - 1 do
  local _, name = reaper.TrackFX_GetParamName(track, i, 10)
  if name == 'Loop companion token' then
    if fx then
      reaper.ShowMessageBox('Select a track containing only one BloomScope.', 'BloomScope', 0)
      return
    end
    fx = i
  end
end
if fx == nil then
  reaper.ShowMessageBox('No companion-capable BloomScope on the selected track.', 'BloomScope', 0)
  return
end
local guid = reaper.TrackFX_GetFXGUID(track, fx)
reaper.gmem_attach(NS)
local now = reaper.time_precise()
local old_token = math.floor(reaper.TrackFX_GetParam(track, fx, 10))
if old_token > 0 then
  local b = (old_token % SLOTS) * STRIDE
  if reaper.gmem_read(b + 1) == old_token and now - reaper.gmem_read(b + 10) < 2 then return end
end
local slot
for i = 0, SLOTS - 1 do
  local b = i * STRIDE
  if reaper.gmem_read(b + 1) == 0 or now - reaper.gmem_read(b + 10) >= 2 then slot = i; break end
end
if slot == nil then
  reaper.ShowMessageBox('All loop context slots are occupied.', 'BloomScope', 0)
  return
end
local base = slot * STRIDE
local token = math.random(1, 16000000) * SLOTS + slot
local nonce, config, heartbeat, previous = nil, 0, 0, ''
local started = now
publish(base, {token, 0, 0, 0, 0, 0, 0, config, heartbeat, now})
reaper.gmem_write(base + 16, 0)
reaper.TrackFX_SetParam(track, fx, 10, token)

local function locate()
  if not reaper.ValidatePtr2(project, track, 'MediaTrack*') then return nil end
  for i = 0, reaper.TrackFX_GetCount(track) - 1 do
    if reaper.TrackFX_GetFXGUID(track, i) == guid then return i end
  end
end
local function finish()
  reaper.gmem_attach(NS)
  if reaper.gmem_read(base + 1) == token then
    publish(base, {token, nonce or 0, 0, 0, 0, 0, 0, config + 1, heartbeat + 1, 0})
  end
end
reaper.atexit(finish)
local function tick()
  reaper.gmem_attach(NS)
  local index = locate()
  if index == nil or reaper.gmem_read(base + 1) ~= token then return end
  if math.floor(reaper.TrackFX_GetParam(track, index, 10)) ~= token then return end
  local current_nonce = reaper.gmem_read(base + 16)
  if current_nonce > 0 and not nonce then nonce = current_nonce end
  -- A new nonce means recompile or colliding instance: require an explicit restart.
  if nonce and current_nonce ~= nonce then return end
  now = reaper.time_precise()
  if not nonce and now - started > 5 then return end
  local a, b = reaper.GetSet_LoopTimeRange2(project, false, true, 0, 0, false)
  local device_ok, rate = reaper.GetAudioDeviceInfo('SRATE')
  rate = (device_ok and tonumber(rate)) or 0
  local enabled = nonce and reaper.EnumProjects(-1) == project and
    reaper.TrackFX_GetEnabled(track, index) and not reaper.TrackFX_GetOffline(track, index) and
    reaper.GetSetRepeatEx(project, -1) == 1 and reaper.Master_GetPlayRate(project) == 1 and
    reaper.Master_GetPlayRateAtTime(reaper.GetPlayPositionEx(project), project) == 1 and
    b > a and rate > 0
  local signature = table.concat({a, b, rate, enabled and 1 or 0}, ':')
  if signature ~= previous then config = config + 1; previous = signature end
  heartbeat = heartbeat + 1
  publish(base, {token, nonce or 0, enabled and 1 or 0, a, b, rate,
    reaper.TimeMap2_timeToQN(project, a), config, heartbeat, now})
  reaper.defer(tick)
end
tick()
