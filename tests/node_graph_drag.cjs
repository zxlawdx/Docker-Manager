/* Smoke test of real DockerFlow handlers: no jsdom/browser/network needed.
   A fake DOM dispatches mouse/touch PointerEvents in both canvas modes. */
"use strict";
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const {resolve} = require("node:path");

class Element {
  constructor(id) {
    this.id=id;this.events={};this.style={};this.dataset={};
    this.children=[];this.value="";this.hidden=false;this._html="";
    this.classList={add(){},remove(){},toggle(){},contains(){return true;}};
  }
  addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
  async fire(name,event){for(const fn of this.events[name]||[])await fn(event);}
  setAttribute(){}
  getBoundingClientRect(){return {left:0,top:0,width:1280,height:800};}
  querySelector(){return null;}
  closest(){return null;}
  set innerHTML(markup){
    this._html=markup;
    if(this.id==="df-nodes"){
      this.children=[...markup.matchAll(/data-id="([^"]+)"/g)].map(match=>{
        const node=new Element("rendered-node");node.dataset.id=match[1];return node;
      });
    }
  }
  get innerHTML(){return this._html;}
}
const elements=new Map();
const document={
  getElementById(id){if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);},
  querySelectorAll(){return [];},
  addEventListener(){}
};
const storage=new Map();
const localStorage={
  getItem(k){return storage.get(k)??null;},
  setItem(k,v){storage.set(k,v);}
};
const window={
  events:{},
  addEventListener(name,fn){(this.events[name]??=[]).push(fn);},
  async fire(name,event){for(const fn of this.events[name]||[])await fn(event);}
};
const js=readFileSync(resolve(__dirname,"../apps/dockerflow/static/js/graph.js"),"utf8");
new Function("window","document","localStorage","setTimeout",js)(
  window,document,localStorage,setTimeout
);
const calls=[];
let responses=[{name:"web",image:"nginx:alpine"},{name:"backend",image:""}];
const deps={
  toast(){},
  ask:async()=>responses.shift()||null,
  api:async(url,method,payload)=>{calls.push({url,method,payload});return {ok:true};},
  download(){},navigate(){},refresh(){},openTerminal(){},showOutput(){}
};
const graph=window.DockerGraph(deps);
function event(id,x,y,options={}){
  const target={closest(selector){
    if(selector==="[data-port]")return null;
    if(selector===".df-graph-node")return {dataset:{id}};
    return null;
  }};
  return {target,pointerId:options.pointerId??7,clientX:x,clientY:y,
    pointerType:options.pointerType??"mouse",button:0,cancelable:true,
    preventDefault(){},stopPropagation(){}};
}
async function main(){
  const layer=document.getElementById("df-nodes"),
        stage=document.getElementById("df-stage");
  const web=await graph.addDraft("container",100,100);
  const x=graph.getState().nodes[0].x;
  await layer.fire("pointerdown",event(web.id,140,140));
  await window.fire("pointermove",event(web.id,240,140));
  assert.equal(graph.getState().nodes[0].x,x+100,
    "Dragging should move node in real-time, not just cursor");
  await window.fire("pointerup",event(web.id,240,140));
  assert.equal(graph.getState().nodes[0].x,x+100,"Drop should persist new position");

  const empty={closest(){return null;}};
  const panEvent=(x,y)=>({...event(null,x,y,{pointerId:8}),target:empty});
  const oldPan=graph.getState().pan.x;
  await stage.fire("pointerdown",panEvent(200,150));
  await window.fire("pointermove",panEvent(255,155));
  assert.equal(graph.getState().pan.x,oldPan+55,"Empty overlay must pan on drag");
  await window.fire("pointerup",panEvent(255,155));

  const network=await graph.addDraft("network",340,200);
  document.getElementById("df-network-view")
    .onchange({target:{value:"zones"}});
  const state=graph.getState();
  const n=state.nodes.find(x=>x.id===network.id);
  const c=state.nodes.find(x=>x.id===web.id);
  assert.ok(n&&c);
  const startX=c.x*state.zoom+state.pan.x+20,startY=c.y*state.zoom+state.pan.y+20;
  const endX=(n.x+70)*state.zoom+state.pan.x,endY=(n.y+120)*state.zoom+state.pan.y;
  await layer.fire("pointerdown",event(c.id,startX,startY,{pointerId:9}));
  await window.fire("pointermove",event(c.id,endX,endY,{pointerId:9}));
  await window.fire("pointerup",event(c.id,endX,endY,{pointerId:9}));
  assert.ok(state.edges.some(e=>e.source===n.id&&e.target===c.id&&!e.persisted),
    "Dropping into network zone should create only a pending relationship");
  assert.equal(calls.length,0,"Canvas drag must never modify Docker automatically");

  responses.push({name:"secure",image:"postgres:16"});
  document.getElementById("df-project").value="dockerflow";
  const passwordNode=await graph.addDraft("container",500,100);
  const userActions=document.getElementById("df-inspector-content");
  responses.push({env:"POSTGRES_PASSWORD",secret:"DB_PASSWORD",password:"never-in-diagram"});
  await userActions.fire("click",{
    target:{closest(selector){return selector==="[data-graph-action]"?
      {dataset:{graphAction:"configure-secret"}}:null;}}
  });
  assert.ok(calls.some(v=>v.url==="/compose/variables/set"));
  const draft=graph.getState().nodes.find(x=>x.id===passwordNode.id);
  assert.equal(JSON.parse(draft.env_text).POSTGRES_PASSWORD,"${DB_PASSWORD}");
  assert.ok(!JSON.stringify(graph.getState()).includes("never-in-diagram"),
    "Secrets must not be saved in graph history/exportable data");
  console.log("Graph interaction smoke: node drag, pan, zone drop, secret reference OK");
}
main().catch(err=>{console.error(err);process.exitCode=1;});
