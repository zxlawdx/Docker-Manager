/* Laboratório visual: grafo como modelo, Docker como fonte de verdade.
   Arestas apenas planejadas até o usuário confirmar "Aplicar". */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value == null ? "" : value).replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const uid = () => "draft-" + Math.random().toString(36).slice(2,10);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  window.DockerGraph = function (deps) {
    const state = {nodes:[],edges:[],removed:[],linking:null,selected:null,
      pan:{x:65,y:46},zoom:1,activeDrag:null,origin:null};
    const world = $("df-world"), stage = $("df-stage"), layer = $("df-nodes");
    const inspector = $("df-inspector-content"), svg = $("df-edges");

    function persistPositions() {
      try {
        const positions = {};
        state.nodes.forEach(n => positions[n.id] = {x:n.x,y:n.y});
        localStorage.setItem("dockerflow.graph.position.v2", JSON.stringify(positions));
      } catch (_) {}
    }
    function storedPositions() {
      try { return JSON.parse(localStorage.getItem("dockerflow.graph.position.v2") || "{}"); }
      catch (_) {return {};}
    }
    function node(id) {return state.nodes.find(n => n.id === id);}
    function normalizeEdge(a,b,real) {
      const na=node(a), nb=node(b);
      if (!na || !nb || na.kind===nb.kind) return false;
      const source=na.kind==="network"?na.id:nb.id, target=na.kind==="container"?na.id:nb.id;
      if (state.edges.some(e=>e.source===source && e.target===target)) return false;
      state.edges.push({id:uid(),source,target,persisted:!!real});
      return true;
    }
    function draftCount() {
      return state.nodes.filter(n=>!n.existing).length +
        state.edges.filter(e=>!e.persisted).length + state.removed.length;
    }
    function updateStatus() {
      $("df-pending-count").textContent=String(draftCount());
      $("df-graph-subtitle").textContent=state.nodes.length+" blocos • "+
        state.edges.length+" conexões"+(draftCount()?" • "+draftCount()+" alterações pendentes":"");
    }
    function transform() {
      world.style.transform="translate("+state.pan.x+"px,"+state.pan.y+"px) scale("+state.zoom+")";
      $("df-zoom-label").textContent=Math.round(state.zoom*100)+"%";
    }
    function clearSelection() {state.selected=null; render();}
    function render() {
      transform();
      layer.innerHTML = state.nodes.map(n => {
        const selected=state.selected && state.selected.type==="node" && state.selected.id===n.id;
        const symbol=n.kind==="network"?"⌘":"⬡";
        const meta=n.kind==="network"?(n.driver||"bridge")+" · Docker network":
          (n.image||"Imagem não definida");
        const status=n.kind==="network"?
          (n.existing?"Rede existente":"Nova rede planejada"):
          (n.existing?(n.status||"desconhecido"):"Container planejado");
        return '<article class="df-graph-node '+esc(n.kind)+(n.existing?'':' draft')+
          (selected?' selected':'')+'" data-id="'+esc(n.id)+'" style="left:'+Number(n.x)+
          'px;top:'+Number(n.y)+'px"><div class="df-node-bar"></div><div class="df-node-body">'+
          '<div class="df-node-top"><span class="df-node-symbol">'+symbol+'</span><div style="min-width:0">'+
          '<div class="df-node-title" title="'+esc(n.name)+'">'+esc(n.name)+'</div>'+
          '<div class="df-node-meta" title="'+esc(meta)+'">'+esc(meta)+'</div></div></div>'+
          '<div class="df-node-status">'+esc(status)+'</div></div>'+
          '<button class="df-port'+(state.linking===n.id?' armed':'')+
          '" title="Conectar a outro bloco" data-port="'+esc(n.id)+'"></button></article>';
      }).join("");
      svg.innerHTML=state.edges.map(e=>{
        const a=node(e.source),b=node(e.target);
        if(!a||!b) return "";
        const x1=a.x+(a.kind==="container"?174:0),y1=a.y+46;
        const x2=b.x+(b.kind==="container"?174:0),y2=b.y+46;
        const delta=Math.max(65,Math.abs(x2-x1)*.52);
        const d="M "+x1+" "+y1+" C "+(x1+(x2>x1?delta:-delta))+" "+y1+", "+
          (x2-(x2>x1?delta:-delta))+" "+y2+", "+x2+" "+y2;
        const selected=state.selected?.type==="edge"&&state.selected.id===e.id;
        return '<path d="'+d+'" fill="none" stroke="'+(selected?"#cfaa58":e.persisted?"#7fb68c":"#aebdaa")+
          '" stroke-width="'+(selected?4:2.4)+'" stroke-dasharray="'+(e.persisted?"0":"6 6")+
          '" data-edge="'+esc(e.id)+'" />';
      }).join("");
      renderInspector();
      updateStatus();
    }
    function field(label,value,attribute,disabled=false) {
      return '<label class="df-field">'+esc(label)+'<input data-edit="'+esc(attribute)+
        '" '+(disabled?'disabled ':'')+'value="'+esc(value)+'"></label>';
    }
    function renderInspector() {
      const selected=state.selected;
      if (!selected) {
        inspector.className="df-inspector-empty";
        inspector.textContent="Selecione um bloco ou uma conexão para ver propriedades e opções.";
        $("df-selection-tip").textContent=state.linking?"Clique no conector do segundo bloco":"Nenhum elemento selecionado";
        return;
      }
      inspector.className="df-inspect-card";
      if (selected.type==="edge") {
        const edge=state.edges.find(e=>e.id===selected.id);
        if (!edge) return clearSelection();
        inspector.innerHTML='<p class="df-eyebrow">CONEXÃO</p><h3>'+esc(node(edge.target)?.name)+
          ' ↔ '+esc(node(edge.source)?.name)+'</h3><p>'+(edge.persisted?
            "Rede ativa no Docker. Remover esta ligação criará uma desconexão pendente.":
            "Ligação planejada; ainda não altera o Docker.")+'</p>'+
          '<button class="df-btn df-btn-warn" data-graph-action="remove-edge">Remover conexão</button>';
        return;
      }
      const n=node(selected.id);
      if (!n) return clearSelection();
      $("df-selection-tip").textContent=(n.kind==="container"?"Container · ":"Rede · ")+n.name;
      inspector.innerHTML='<p class="df-eyebrow">PROPRIEDADES / '+esc(n.kind.toUpperCase())+
        '</p><h3>'+esc(n.name)+'</h3>'+field("Nome",n.name,"name",n.existing)+
        (n.kind==="container"?field("Imagem",n.image||"","image",n.existing):
          '<label class="df-field">Driver<input value="bridge" disabled></label>'+
          (!n.existing?'<label class="df-field"><span><input style="width:auto" type="checkbox" data-internal '+
            (n.internal?'checked':'')+'> Somente interna</span></label>':""))+
        '<div class="df-inspect-value">'+(n.existing?"DOCKER ID "+esc(n.dockerId||""):"RASCUNHO • NÃO CRIADO")+
        '</div>'+(n.kind==="container" && n.existing?
          '<button class="df-btn df-btn-subtle" data-graph-action="terminal">Abrir terminal ↗</button>':"")+
        '<button class="df-btn df-btn-warn" data-graph-action="delete-node">'+
        (n.existing?"Retirar do diagrama":"Excluir bloco")+'</button>'+
        (n.kind==="network" && n.existing && !["bridge","host","none"].includes(n.name)?
          '<button class="df-btn df-btn-warn" data-graph-action="delete-network">Excluir rede do Docker</button>':"");
    }
    async function addDraft(kind,x,y) {
      const isNet=kind==="network";
      const values=await deps.ask({
        title:isNet?"Nova rede bridge":"Novo container",
        description:isNet?"Crie um bloco de rede. A rede só existirá após Aplicar.":
          "Defina um container planejado. O Docker só será alterado ao aplicar.",
        fields:isNet?[{key:"name",label:"Nome",value:"minha-rede"}]:
          [{key:"name",label:"Nome",value:"novo-servico"},
           {key:"image",label:"Imagem Docker",value:"nginx:alpine"}]
      });
      if (!values) return;
      const n={id:uid(),kind,name:values.name.trim()||"sem-nome",
        x:Math.round(x),y:Math.round(y),existing:false,driver:"bridge",
        image:values.image?.trim()||"",internal:false};
      if(state.nodes.some(o=>o.name===n.name&&o.kind===n.kind)) return deps.toast("Nome já usado no desenho",true);
      state.nodes.push(n);state.selected={type:"node",id:n.id};persistPositions();render();
    }
    async function connect(a,b) {
      if (a===b) return deps.toast("Escolha outro bloco",true);
      const na=node(a),nb=node(b);
      if (!na||!nb) return;
      if (na.kind==="network"&&nb.kind==="network")
        return deps.toast("Conecte redes a containers, não redes diretamente.",true);
      if (na.kind==="container"&&nb.kind==="container") {
        const out=await deps.ask({title:"Compartilhar uma rede",
          description:"A ligação de dois containers no Docker é representada por uma rede bridge. Qual nome dar a ela?",
          fields:[{key:"name",label:"Rede nova",value:"rede-"+na.name+"-"+nb.name}]});
        if(!out) return;
        const name=out.name.trim();
        if(!name || state.nodes.some(n=>n.kind==="network"&&n.name===name))
          return deps.toast("Nome de rede vazio ou duplicado",true);
        const network={id:uid(),kind:"network",name,driver:"bridge",existing:false,
          x:Math.round((na.x+nb.x)/2+80),y:Math.round((na.y+nb.y)/2-130)};
        state.nodes.push(network);
        normalizeEdge(network.id,na.id,false);normalizeEdge(network.id,nb.id,false);
      } else {
        if (!normalizeEdge(a,b,false)) return deps.toast("Essa ligação já existe",true);
      }
      state.selected=null;render();
    }

    async function loadExample() {
      if(draftCount() && !(await deps.ask({
        title:"Abrir o exemplo de rede?",
        description:"Isso substituirá os blocos desenhados que ainda não foram aplicados. Exporte JSON para guardar seu rascunho.",
        fields:[]
      })))return;
      const uidNet=uid(),uidWeb=uid(),uidDb=uid();
      state.nodes=[
        {id:uidWeb,kind:"container",name:"minha-api",image:"nginx:alpine",
          existing:false,driver:"bridge",x:88,y:170},
        {id:uidNet,kind:"network",name:"lab-backend",driver:"bridge",
          existing:false,x:345,y:172,internal:false},
        {id:uidDb,kind:"container",name:"redis-cache",image:"redis:7-alpine",
          existing:false,driver:"bridge",x:610,y:170}
      ];
      state.edges=[
        {id:uid(),source:uidNet,target:uidWeb,persisted:false},
        {id:uid(),source:uidNet,target:uidDb,persisted:false}
      ];
      state.removed=[];state.selected=null;state.linking=null;
      state.zoom=.85;state.pan={x:25,y:35};persistPositions();render();
      deps.toast("Exemplo editável carregado. O Docker ainda não foi alterado.");
    }

    async function importDocker(force=false) {
      if (!force && draftCount() && !(await deps.ask({title:"Substituir o rascunho?",
          description:"A importação descartará alterações NÃO aplicadas. Exporte JSON antes, se necessário.",fields:[]}))) return;
      const [containers,networks]=await Promise.all([deps.api("/containers"),deps.api("/networks")]);
      const positions=storedPositions(),nodes=[],edges=[];
      const ids=new Map();
      containers.forEach((c,i)=>{
        const id="container:"+c.id, p=positions[id]||{x:90,y:80+(i%9)*139};
        nodes.push({id,dockerId:c.id,kind:"container",name:c.name,image:c.image,status:c.status,
          x:p.x,y:p.y,existing:true});ids.set(c.id,id);
      });
      networks.forEach((n,i)=>{
        const id="network:"+n.id,p=positions[id]||{x:450+(i%2)*290,y:92+Math.floor(i/2)*170};
        nodes.push({id,dockerId:n.id,kind:"network",name:n.name,driver:n.driver,
          x:p.x,y:p.y,existing:true});
        (n.containers||[]).forEach(c=>{
          const container=ids.get(c.id);
          if(container)edges.push({id:uid(),source:id,target:container,persisted:true});
        });
      });
      state.nodes=nodes;state.edges=edges;state.removed=[];state.selected=null;state.linking=null;
      render();persistPositions();deps.toast("Topologia importada do Docker");
    }
    function removeSelected() {
      if(!state.selected)return;
      if(state.selected.type==="edge") {
        const e=state.edges.find(x=>x.id===state.selected.id);
        if (e?.persisted) state.removed.push({source:e.source,target:e.target});
        state.edges=state.edges.filter(x=>x.id!==state.selected.id);
      } else {
        const id=state.selected.id,n=node(id);
        if(!n) return;
        if(n.existing) {
          // Retirar um bloco existente do desenho NÃO remove nada no daemon.
          const affected=state.edges.filter(e=>e.source===id||e.target===id);
          // Não programar desconexão pela simples ocultação de um bloco.
          state.edges=state.edges.filter(e=>e.source!==id&&e.target!==id);
        } else {
          state.edges=state.edges.filter(e=>e.source!==id&&e.target!==id);
        }
        state.nodes=state.nodes.filter(x=>x.id!==id);
      }
      state.selected=null;render();persistPositions();
    }
    async function apply() {
      if(!draftCount())return deps.toast("Nenhuma alteração pendente");
      const planned=state.nodes.filter(n=>!n.existing);
      const count=state.edges.filter(e=>!e.persisted).length;
      const accepted=await deps.ask({
        title:"Aplicar alterações ao Docker?",
        description:"Será criado: "+planned.length+" bloco(s), conectado: "+count+
          " ligação(ões), desconectado: "+state.removed.length+
          ". Operações são sequenciais; falhas podem deixar parte já aplicada.",fields:[],
        confirmText:"Aplicar ao Docker"
      });
      if(!accepted)return;
      try {
        // 1. Redes antes dos containers: estes podem escolher a rede ao nascer.
        for(const n of planned.filter(x=>x.kind==="network")){
          const result=await deps.api("/networks/action","POST",{action:"create",name:n.name,internal:!!n.internal});
          n.dockerId=result.id;n.existing=true;
        }
        // 2. Containers devem existir antes dos vínculos de rede.
        for(const n of planned.filter(x=>x.kind==="container")){
          const result=await deps.api("/containers/create","POST",
            {name:n.name,image:n.image,network:null,ports:[],volumes:[],environment:{}});
          n.dockerId=result.id;n.existing=true;n.status="running";
        }
        // 3. Aplicar SOMENTE as novas conexões, com id Docker resolvido.
        for(const edge of state.edges.filter(e=>!e.persisted)){
          const network=node(edge.source),container=node(edge.target);
          await deps.api("/networks/action","POST",
            {action:"connect",network:network.dockerId,container:container.dockerId});
          edge.persisted=true;
        }
        for(const edge of state.removed){
          const network=node(edge.source),container=node(edge.target);
          if(network?.dockerId&&container?.dockerId)
            await deps.api("/networks/action","POST",
              {action:"disconnect",network:network.dockerId,container:container.dockerId});
          state.removed=state.removed.filter(e=>e!==edge);
        }
        deps.toast("Topologia aplicada no Docker ✓");render();persistPositions();
        deps.refresh();
      }catch(e){
        deps.toast("Aplicação interrompida: "+e.message+" — confira o Docker e atualize.",true);
        render();deps.refresh();
      }
    }
    async function exportCompose() {
      try{
        const result=await deps.api("/graph/compose","POST",
          {nodes:state.nodes,edges:state.edges});
        deps.setYaml(result.content);
        deps.navigate("ide");
        deps.toast("Compose gerado. Revise o YAML antes de executar.");
      }catch(e){deps.toast(e.message,true);}
    }
    function exportJson(){
      const content=JSON.stringify({version:2,nodes:state.nodes,edges:state.edges},null,2);
      deps.download("dockerflow-topologia.json",content,"application/json");
    }
    async function importJson(file) {
      let data;
      try {data=JSON.parse(await file.text());}
      catch (_) {return deps.toast("Arquivo JSON inválido",true);}
      if(!data||data.version!==2||!Array.isArray(data.nodes)||!Array.isArray(data.edges)||
         data.nodes.length>150||data.edges.length>350)
        return deps.toast("Formato de grafo desconhecido ou excessivo",true);
      const ids=new Set();
      for(const n of data.nodes){
        if(!["container","network"].includes(n.kind)||typeof n.id!=="string"||
           typeof n.name!=="string"||!Number.isFinite(n.x)||!Number.isFinite(n.y)||
           ids.has(n.id))return deps.toast("Arquivo contém blocos inválidos",true);
        ids.add(n.id);
      }
      state.nodes=data.nodes;state.edges=data.edges.filter(e=>
        ids.has(e.source)&&ids.has(e.target)&&typeof e.id==="string");
      state.removed=[];state.selected=null;render();persistPositions();
      deps.toast("Grafo importado. Confirme a ligação real antes de aplicar.");
    }

    // Mouse/pointer: nodes arrastáveis e stage com pan independente.
    layer.addEventListener("pointerdown",e=>{
      const port=e.target.closest("[data-port]");
      if(port){e.preventDefault();e.stopPropagation();return;}
      const el=e.target.closest(".df-graph-node");
      if(!el)return;
      const n=node(el.dataset.id);if(!n)return;
      state.selected={type:"node",id:n.id};
      state.activeDrag={id:n.id,clientX:e.clientX,clientY:e.clientY,x:n.x,y:n.y};
      el.setPointerCapture(e.pointerId);renderInspector();
    });
    layer.addEventListener("pointermove",e=>{
      if(!state.activeDrag)return;
      const drag=state.activeDrag,n=node(drag.id);
      if(!n)return;
      n.x=Math.max(0,drag.x+(e.clientX-drag.clientX)/state.zoom);
      n.y=Math.max(0,drag.y+(e.clientY-drag.clientY)/state.zoom);
      // Sem recriar nodes durante arraste: mantém pointer capture.
      const element=Array.from(layer.children).find(el=>el.dataset.id===n.id);
      if(element){element.style.left=n.x+"px";element.style.top=n.y+"px";}
      // Caminho SVG atualiza sem remover o DOM ativo.
      svg.innerHTML=state.edges.map(edge=>{
        const a=node(edge.source),b=node(edge.target);if(!a||!b)return "";
        const x1=a.x+(a.kind==="container"?174:0),y1=a.y+46;
        const x2=b.x+(b.kind==="container"?174:0),y2=b.y+46;
        const k=Math.max(65,Math.abs(x2-x1)*.52),sign=x2>x1?1:-1;
        return '<path d="M '+x1+' '+y1+' C '+(x1+sign*k)+' '+y1+
          ', '+(x2-sign*k)+' '+y2+', '+x2+' '+y2+
          '" fill="none" stroke="'+(edge.persisted?"#7fb68c":"#aebdaa")+
          '" stroke-width="2.4" stroke-dasharray="'+(edge.persisted?"0":"6 6")+
          '" data-edge="'+esc(edge.id)+'"/>';
      }).join("");
    });
    layer.addEventListener("pointerup",()=>{if(state.activeDrag){state.activeDrag=null;persistPositions();render();}});
    layer.addEventListener("pointercancel",()=>{state.activeDrag=null;});
    layer.addEventListener("click",async e=>{
      const port=e.target.closest("[data-port]");
      if(port){
        e.stopPropagation();
        const id=port.dataset.port;
        if(!state.linking){state.linking=id;render();}
        else {const a=state.linking;state.linking=null;await connect(a,id);render();}
        return;
      }
      const el=e.target.closest("[data-id]");
      if(el){state.selected={type:"node",id:el.dataset.id};render();}
    });
    svg.addEventListener("click",e=>{
      const path=e.target.closest("[data-edge]");
      if(path){state.selected={type:"edge",id:path.dataset.edge};render();}
    });
    stage.addEventListener("pointerdown",e=>{
      if(e.target!==stage)return;
      state.origin={x:e.clientX,y:e.clientY,pX:state.pan.x,pY:state.pan.y};
      stage.setPointerCapture(e.pointerId);
    });
    stage.addEventListener("pointermove",e=>{
      if(!state.origin)return;
      state.pan.x=state.origin.pX+(e.clientX-state.origin.x);
      state.pan.y=state.origin.pY+(e.clientY-state.origin.y);
      transform();
    });
    stage.addEventListener("pointerup",e=>{
      if(state.origin){state.origin=null;stage.releasePointerCapture(e.pointerId);}
    });
    stage.addEventListener("pointercancel",()=>{state.origin=null;});
    stage.addEventListener("wheel",e=>{
      e.preventDefault();const rect=stage.getBoundingClientRect();
      const x=e.clientX-rect.left,y=e.clientY-rect.top;
      const old=state.zoom,next=Math.max(.4,Math.min(1.8,old*(e.deltaY>0?.91:1.09)));
      state.pan.x=x-(x-state.pan.x)*next/old;
      state.pan.y=y-(y-state.pan.y)*next/old;
      state.zoom=next;transform();
    },{passive:false});
    stage.addEventListener("dragover",e=>e.preventDefault());
    stage.addEventListener("drop",async e=>{
      e.preventDefault();const kind=e.dataTransfer.getData("application/dockerflow-node");
      if(!["container","network"].includes(kind))return;
      const rect=stage.getBoundingClientRect();
      await addDraft(kind,(e.clientX-rect.left-state.pan.x)/state.zoom,
        (e.clientY-rect.top-state.pan.y)/state.zoom);
    });
    document.querySelectorAll(".df-palette-item").forEach(el=>{
      el.addEventListener("dragstart",e=>e.dataTransfer.setData("application/dockerflow-node",el.dataset.kind));
      // Também funciona no WebView sem suporte consistente ao dragstart.
      el.addEventListener("dblclick",()=>addDraft(el.dataset.kind,150+Math.random()*130,90+Math.random()*160));
    });
    inspector.addEventListener("change",e=>{
      const n=node(state.selected?.id);
      if(!n||n.existing)return;
      if(e.target.dataset.edit){n[e.target.dataset.edit]=e.target.value;render();}
      if(e.target.hasAttribute("data-internal")){n.internal=e.target.checked;}
    });
    inspector.addEventListener("click",async e=>{
      const action=e.target.closest("[data-graph-action]")?.dataset.graphAction;
      if(!action)return;
      const n=node(state.selected?.id);
      if(action==="remove-edge"||action==="delete-node")return removeSelected();
      if(action==="terminal"&&n){deps.openTerminal(n.dockerId);}
      if(action==="delete-network"&&n){
        const yes=await deps.ask({title:"Excluir rede Docker?",
          description:"A rede será excluída de verdade e não poderá conter containers ativos.",fields:[]});
        if(yes)try{
          await deps.api("/networks/action","POST",{action:"remove",network:n.dockerId});
          removeSelected();deps.toast("Rede removida");deps.refresh();
        }catch(err){deps.toast(err.message,true);}
      }
    });
    $("df-zoom-in").onclick=()=>{state.zoom=Math.min(1.8,state.zoom+.1);transform();};
    $("df-zoom-out").onclick=()=>{state.zoom=Math.max(.4,state.zoom-.1);transform();};
    $("df-zoom-reset").onclick=()=>{state.zoom=1;state.pan={x:65,y:46};transform();};
    $("df-graph-demo").onclick=loadExample;
    $("df-graph-load").onclick=()=>importDocker();
    $("df-graph-apply").onclick=apply;
    $("df-graph-save").onclick=exportJson;
    $("df-graph-compose").onclick=exportCompose;
    $("df-import-file").onclick=()=>$("df-import-input").click();
    $("df-import-input").onchange=e=>{if(e.target.files[0])importJson(e.target.files[0]);e.target.value="";};

    render();
    return {importDocker,exportJson,render,addDraft,apply,getState:()=>state};
  };
})();
