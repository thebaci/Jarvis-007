/* Jarvis 007: deterministic depth, stable note positions and integration contract. */
const assert=require('node:assert/strict');
global.window={JavisGraph:class {}};
require('../../dashboard/brain-spatial.js');
const g=window.JarvisBrainGeometry;
const p=g.memoryPosition('wiki/research/sleep.md');
assert.deepEqual(p,g.memoryPosition('wiki/research/sleep.md'));
assert.notDeepEqual(p,g.memoryPosition('wiki/research/exercise.md'));
for(let i=0;i<5000;i++){const q=g.memoryPosition('memory-'+i);assert(q.every(Number.isFinite));assert(Math.abs(q[0])<225&&Math.abs(q[1])<190&&Math.abs(q[2])<120);}
const near=g.project([30,0,100],0,0,1,800,600,[0,0]);
const far=g.project([30,0,-100],0,0,1,800,600,[0,0]);assert(near.scale>far.scale);
const zoom=g.project([30,0,100],0,0,2,800,600,[0,0]);assert.equal(zoom.scale,near.scale*2);
const turn=g.project([30,0,100],Math.PI/2,0,1,800,600,[0,0]);assert.notEqual(turn.x,near.x);
const pan=g.project([30,0,100],0,0,1,800,600,[10,-5]);assert.equal(pan.x,near.x+10);assert.equal(pan.y,near.y-5);
const fs=require('node:fs');const html=fs.readFileSync(require('node:path').join(__dirname,'../../dashboard/index.html'),'utf8');
assert(html.indexOf('/static/brain-spatial.js')>html.indexOf('/static/graph.js'));
assert(html.includes('/static/brain-spatial.css'));
console.log('Jarvis 007 brain geometry and integration: passed');

// Jarvis 007: classic script consumers must receive the spatial constructor too.
const vm=require('node:vm');const context={window:{}};
vm.runInNewContext('class JavisGraph {}; window.JavisGraph = JavisGraph; '+fs.readFileSync(require('node:path').join(__dirname,'../../dashboard/brain-spatial.js'),'utf8')+'; replacementMatches = JavisGraph === window.JavisGraph;',context);
assert.equal(context.replacementMatches,true);
