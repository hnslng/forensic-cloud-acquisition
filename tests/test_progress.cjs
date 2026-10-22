const test = require('node:test');
const assert = require('node:assert/strict');
const { acquisitionProgress } = require('../frontend/progress.js');
const base = { status:'running', inventory_complete:true, total_known:true, bytes_done:250, bytes_total:1000, files_done:1, files_discovered:4 };
test('known sizes use bytes rather than equal file weights', () => {
  assert.equal(acquisitionProgress({...base,files_done:3}).percent,25);
  assert.equal(acquisitionProgress({...base,bytes_done:800}).percent,80);
});
test('mixed Google exports use verified file count instead of an empty bar', () => {
  const p=acquisitionProgress({...base,total_known:false,bytes_done:338387174,bytes_total:338387174,files_done:16,files_discovered:17});
  assert.equal(p.mode,'files'); assert.ok(p.percent>94 && p.percent<95);
  assert.match(p.label,/16 von 17 Dateien gesichert/); assert.match(p.label,/Gesamtgröße unbekannt/);
});
test('unknown sizes advance as files finish, including zero-byte files', () => {
  const values=[0,1,2,3].map(files_done=>acquisitionProgress({...base,total_known:false,bytes_done:0,files_done}).percent);
  assert.deepEqual(values,[0,25,50,75]);
});
test('open inventory never claims a total percentage, including on pause', () => {
  for(const status of ['running','paused']) {
    const p=acquisitionProgress({...base,status,inventory_complete:false});
    assert.equal(p.percent,null); assert.equal(p.mode,'inventory');
  }
});
test('100 percent and completion reserved for successful final verification', () => {
  assert.equal(acquisitionProgress({...base,bytes_done:1000}).percent,99);
  assert.equal(acquisitionProgress({...base,total_known:false,files_done:4,status:'incomplete'}).percent,99);
  assert.equal(acquisitionProgress({...base,status:'completed'}).percent,100);
});
test('empty unknown inventory and missing job remain honest', () => {
  assert.equal(acquisitionProgress({...base,total_known:false,files_discovered:0}).percent,null);
  assert.equal(acquisitionProgress(null).mode,'unavailable');
});
