/* DockerFlow SPA para o Vela 0.2.2; ações de daemon exigem interação.
   API local sem gRPC, sem CDN, sem módulos npm e compatível com PyWebView. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g,
    c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const app = {mounted:false,page:"graph",overview:{online:false},graph:null,
    terminal:null,pollTimer:null,editorMode:"compose",containers:[],networks:[]};
  const titles={overview:"Visão geral",graph:"Laboratório visual",
    containers:"Containers",images:"Imagens",networks:"Redes",volumes:"Volumes",tasks:"Tarefas",monitor:"Monitoramento",audit:"Auditoria",logs:"Logs",ide:"Compose IDE",terminal:"Terminal Docker"};

  async function api(path,method="GET",payload=null){
    const opts={method,headers:{"Accept":"application/json",
      "X-DockerFlow-Token":$("dockerflow-root").dataset.apiToken}};
    if(payload!==null){opts.headers["Content-Type"]="application/json";opts.body=JSON.stringify(payload);}
    const response=await fetch("/api"+path,opts);
    const result=await response.json();
    if(!response.ok || result?.error) throw new Error(result?.error||"Falha HTTP "+response.status);
    if(result?.task_id && path!=="/tasks/status"){
      toast("Tarefa iniciada: "+result.task_id.slice(0,8));
      while(true){
        await new Promise(resolve=>setTimeout(resolve,650));
        const task=await api("/tasks/status","POST",{id:result.task_id});
        if(task.state==="failed")throw new Error(task.error||"Falha na operação Docker");
        if(task.state==="cancelled")throw new Error("Tarefa cancelada");
        if(task.state==="done")return task.result;
      }
    }
    return result;
  }
  function toast(message,error=false){
    const box=$("df-notify"),item=document.createElement("div");
    item.className="df-toast"+(error?" error":"");item.textContent=message;box.appendChild(item);
    setTimeout(()=>item.remove(),5000);
  }
  function download(name,content,type){
    const object=URL.createObjectURL(new Blob([content],{type:type||"text/plain;charset=utf-8"}));
    const a=document.createElement("a");a.href=object;a.download=name;document.body.appendChild(a);
    a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(object),800);
  }
  function ask({title,description="",fields=[],confirmText="Confirmar"}){
    return new Promise(resolve=>{
      const modal=$("df-modal"),form=$("df-modal-form");
      $("df-modal-title").textContent=title;
      $("df-modal-description").textContent=description;
      $("df-modal-fields").innerHTML=fields.map(f=>
        '<label class="df-field">'+esc(f.label)+
          '<input data-modal-key="'+esc(f.key)+'" value="'+esc(f.value||"")+
          '" '+(f.type?'type="'+esc(f.type)+'"':"")+' autocomplete="off"></label>').join("");
      $("df-modal-confirm").textContent=confirmText;
      const complete=()=>{
        if(modal.returnValue!=="confirm")return resolve(null);
        const result={};
        modal.querySelectorAll("[data-modal-key]").forEach(i=>result[i.dataset.modalKey]=i.value);
        resolve(result);
      };
      modal.addEventListener("close",complete,{once:true});
      modal.returnValue="";
      if(!modal.open) modal.showModal();
    });
  }
  async function confirmed(title,description,confirmText="Confirmar"){
    return !!(await ask({title,description,confirmText,fields:[]}));
  }
  function showOutput(title,text){
    const modal=$("df-modal");
    $("df-modal-title").textContent=title;
    $("df-modal-description").textContent="Saída limitada para manter o aplicativo responsivo.";
    $("df-modal-fields").innerHTML="";
    const pre=document.createElement("pre");pre.className="df-inspect-value";
    pre.style.maxHeight="52vh";pre.style.overflow="auto";pre.textContent=String(text);
    $("df-modal-fields").append(pre);$("df-modal-confirm").textContent="Fechar";
    modal.returnValue="";if(!modal.open)modal.showModal();
  }
  function navigate(page){
    if(!titles[page])return;
    app.page=page;
    document.querySelectorAll("[data-content]").forEach(el=>{
      const visible=el.dataset.content===page;el.classList.toggle("visible",visible);
      el.hidden=!visible;
    });
    document.querySelectorAll(".df-nav-item").forEach(el=>el.classList.toggle("active",el.dataset.page===page));
    $("df-breadcrumb-current").textContent=titles[page];
    if(page==="containers")loadContainers();
    if(page==="images")loadImages();
    if(page==="volumes")loadVolumes();
    if(page==="networks")loadNetworks();
    if(page==="tasks")loadTasks();
    if(page==="monitor")loadMonitor();
    if(page==="audit")loadAudit();
    if(page==="logs")loadLogContainers();
    if(page==="terminal")refreshTerminalList();
    if(page==="ide")listProjects();
  }
  function setYaml(text){$("df-yaml").value=text;switchEditor("compose");}
  function renderOverview(){
    const o=app.overview;
    $("df-engine-status").textContent=o.online?"Engine v"+(o.engine||"?"):"Docker offline";
    $("df-host-text").textContent=o.online?"Conectado localmente":"Indisponível";
    $("df-engine-dot").classList.toggle("online",o.online);
    $("df-host-dot").classList.toggle("online",o.online);
    $("df-metrics").innerHTML=[
      ["Containers",o.containers],["Em execução",o.running],
      ["Imagens",o.images],["Redes",o.networks],["Volumes",o.volumes]
    ].map(item=>'<div class="df-metric"><small>'+esc(item[0])+'</small><strong>'+
      esc(item[1]??"—")+'</strong></div>').join("");
    if(!o.online&&o.message)toast("Docker: "+o.message,true);
  }
  async function refresh(){
    try{app.overview=await api("/overview");renderOverview();}
    catch(err){app.overview={online:false,message:err.message};renderOverview();}
    if(app.page==="containers")await loadContainers();
    if(app.page==="images")await loadImages();
    if(app.page==="volumes")await loadVolumes();
    if(app.page==="networks")await loadNetworks();
    if(app.page==="tasks")await loadTasks();
    if(app.page==="logs")await loadLogContainers();
  }
  function rowButton(action,label,id,extra=""){
    return '<button class="df-mini-btn '+esc(extra)+'" data-action="'+esc(action)+'" data-id="'+esc(id)+
      '">'+esc(label)+'</button>';
  }
  async function loadContainers(){
    try {
      app.containers=await api("/containers");const rows=app.containers;
      $("df-container-total").textContent=rows.length;
      $("df-container-list").innerHTML='<table class="df-table"><thead><tr><th>Nome</th><th>Imagem</th>'+
        '<th>Estado</th><th>Redes</th><th>Ações</th></tr></thead><tbody>'+
        rows.map(c=>'<tr><td><b>'+esc(c.name)+'</b><small>'+esc(c.id.slice(0,12))+'</small></td>'+
          '<td>'+esc(c.image)+'</td><td><span class="df-badge '+
          (c.status==="running"?"":"stopped")+'">'+esc(c.status)+'</span></td>'+
          '<td>'+esc(c.networks.join(", ")||"—")+'</td><td><div class="df-row-actions">'+
          rowButton(c.status==="running"?"stop":"start",c.status==="running"?"Parar":"Iniciar",c.id)+
          rowButton("restart","Reiniciar",c.id)+rowButton("logs","Logs",c.id)+
          rowButton("inspect","Inspecionar",c.id)+rowButton("exec","Terminal",c.id)+
          rowButton("remove","Remover",c.id,"danger")+"</div></td></tr>").join("")+
          '</tbody></table>'+(rows.length?"":'<div class="df-empty">Nenhum container encontrado.</div>');
    }catch(err){$("df-container-list").innerHTML='<div class="df-empty">'+esc(err.message)+'</div>';}
  }
  async function containerAction(action,id){
    if(action==="exec")return openTerminal(id);
    if(action==="logs"){
      try{const result=await api("/containers/logs","POST",{id,tail:250});
        showOutput("Logs do container",result.logs||"Sem logs");}
      catch(err){toast(err.message,true);}return;
    }
    if(action==="inspect"){
      try{const result=await api("/containers/inspect","POST",{id});
        showOutput("Inspeção (segredos omitidos)",JSON.stringify(result,null,2));}
      catch(err){toast(err.message,true);}return;
    }
    if(action==="remove"){
      if(!(await confirmed("Remover container?","Operação destrutiva. Pare antes de remover. Volumes nomeados não serão removidos.","Remover")))return;
    }
    try{await api("/containers/action","POST",{action,id});toast("Ação executada: "+action);
      await loadContainers();await refresh();}
    catch(err){toast(err.message,true);}
  }
  async function createContainer(){
    const f=await ask({title:"Criar container",description:"Configure uma instância real do Docker. Campos avançados em JSON.",
      fields:[{key:"name",label:"Nome",value:"web-lab"},
        {key:"image",label:"Imagem",value:"nginx:alpine"},
        {key:"host",label:"Porta do host (opcional)",value:"8080"},
        {key:"internal",label:"Porta do container",value:"80"},
        {key:"network",label:"Rede existente (opcional)"},
        {key:"environment",label:'Variáveis JSON, ex.: {"TZ":"UTC"}',value:"{}"},
        {key:"volumes",label:'Volumes JSON, ex.: [{"source":"dados","target":"/data"}]',value:"[]"},
        {key:"cpus",label:"Limite de CPUs (opcional)",value:""},
        {key:"memory_mb",label:"Limite de memória MiB (opcional)",value:""},
        {key:"restart",label:"Restart (no/always/unless-stopped/on-failure)",value:"unless-stopped"},
        {key:"read_only",label:"Filesystem somente leitura? 1=sim, 0=não",value:"0"}],
      confirmText:"Criar"});
    if(!f)return;
    try{
      const environment=JSON.parse(f.environment||"{}"),volumes=JSON.parse(f.volumes||"[]");
      const ports=f.host?[{host:f.host,container:f.internal}]:[];
      await api("/containers/create","POST",
        {name:f.name,image:f.image,network:f.network,environment,volumes,ports,
         cpus:f.cpus,memory_mb:f.memory_mb,restart:f.restart,read_only:f.read_only==="1"});
      toast("Container criado");await refresh();
    }catch(err){toast(err.message,true);}
  }
  async function loadImages(){
    try{
      const list=await api("/images");
      $("df-image-list").innerHTML='<div style="padding:12px 21px"><button class="df-btn df-btn-subtle" id="df-image-build">◫ Construir a partir de Dockerfile</button></div>'+
      '<table class="df-table"><thead><tr><th>Imagem</th><th>ID</th><th>Tamanho</th><th>Ação</th></tr></thead><tbody>'+
      list.map(i=>'<tr><td><b>'+esc((i.tags||[]).join(", ")||"<sem tag>")+'</b></td>'+
       '<td>'+esc(i.id.slice(0,23))+'</td><td>'+((Number(i.size)||0)/1048576).toFixed(1)+' MB</td>'+
       '<td>'+rowButton("image-history","Camadas",i.id)+
        rowButton("image-tag","Criar tag",i.id)+
        rowButton("image-remove","Remover",i.id,"danger")+'</td></tr>').join("")+
      '</tbody></table>'+(list.length?"":'<div class="df-empty">Nenhuma imagem local.</div>');
      $("df-image-build").onclick=buildImage;
    }catch(err){$("df-image-list").innerHTML='<div class="df-empty">'+esc(err.message)+'</div>';}
  }
  async function pullImage(){
    const f=await ask({title:"Baixar imagem",fields:[{key:"image",label:"Referência",value:"nginx:alpine"}]});
    if(!f)return;toast("Iniciando pull: "+f.image);
    try{await api("/images/action","POST",{action:"pull",image:f.image});
      toast("Imagem baixada");await refresh();}
    catch(err){toast(err.message,true);}
  }
  async function buildImage(){
    const f=await ask({title:"Construir imagem",description:"Informe um diretório NO MESMO host do DockerFlow que contenha Dockerfile.",
      fields:[{key:"path",label:"Diretório de build",value:""},
              {key:"tag",label:"Tag de destino",value:"minha-imagem:dev"}],confirmText:"Build"});
    if(!f)return;
    try{const result=await api("/images/action","POST",
      {action:"build",path:f.path,tag:f.tag});
      showOutput("Docker build",result.log||"Build concluído");await refresh();}
    catch(err){toast(err.message,true);}
  }
  async function removeImage(id){
    if(!(await confirmed("Remover imagem?","Contêineres dependentes podem bloquear esta operação.","Remover")))return;
    try{await api("/images/action","POST",{action:"remove",image:id});toast("Imagem removida");await refresh();}
    catch(err){toast(err.message,true);}
  }




  // Os logs são snapshots sob demanda; não manter polling em containers de produção.
  let logSnapshot="",logContainerName="";
  async function loadLogContainers(){
    try {
      const containers=await api("/containers"),el=$("df-log-container"),selected=el.value;
      el.innerHTML=containers.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join("");
      if(containers.some(c=>c.id===selected))el.value=selected;
      if(!containers.length)$("df-log-output").textContent="Nenhum container disponível.";
    }catch(err){$("df-log-output").textContent=err.message;}
  }
  function filterLogs(){
    const q=$("df-log-filter").value.toLocaleLowerCase("pt-BR");
    const lines=logSnapshot.split("\n"),matched=q?lines.filter(line=>line.toLocaleLowerCase("pt-BR").includes(q)):lines;
    $("df-log-output").textContent=matched.join("\n").slice(-150000);
  }
  async function fetchLogs(){
    const id=$("df-log-container").value;
    if(!id)return toast("Selecione um container",true);
    $("df-log-output").textContent="Consultando...";
    try {
      const result=await api("/containers/logs","POST",{id,tail:Number($("df-log-tail").value)});
      logSnapshot=result.logs||"";
      logContainerName=$("df-log-container").selectedOptions[0]?.textContent||"container";
      filterLogs();
    }catch(err){$("df-log-output").textContent=err.message;toast(err.message,true);}
  }
  function exportLogs(){
    if(!logSnapshot)return toast("Consulte os logs primeiro",true);
    const safeName=logContainerName.replace(/[^a-z0-9_-]/gi,"_").slice(0,40);
    download("dockerflow-"+safeName+"-logs.txt", $("df-log-output").textContent,"text/plain;charset=utf-8");
  }
  async function loadAudit(){
    const box=$("df-audit-list");box.textContent="Analisando os containers...";
    try {
      const audit=await api("/audit/containers");
      box.innerHTML='<table class="df-table"><thead><tr><th>Container</th><th>Estado</th><th>Verificações</th></tr></thead><tbody>'+
        audit.containers.map(c=>'<tr><td><b>'+esc(c.name)+'</b></td><td>'+esc(c.status)+'</td><td>'+
          (c.notes.length?c.notes.map(note=>'<p>'+esc(note)+'</p>').join(""):"Nenhum sinal detectado")+
          '</td></tr>').join("")+'</tbody></table><div class="df-empty">'+esc(audit.note)+'</div>';
    } catch(err){box.textContent=err.message;}
  }
  async function imageCleanup(){
    try {
      const preview=await api("/images/action","POST",{action:"prune-preview"});
      if(!preview.count)return toast("Nenhuma imagem dangling encontrada.");
      if(!(await confirmed("Limpar imagens dangling?",
        preview.count+" imagem(ns) sem tag. O espaço recuperado depende de camadas compartilhadas.",
        "Limpar")))return;
      const result=await api("/images/action","POST",{action:"prune"});
      toast("Espaço recuperado segundo Docker: "+(Number(result.space_reclaimed)/1048576).toFixed(1)+" MiB");
      await loadImages();
    } catch(err){toast(err.message,true);}
  }
  async function scanUnusedVolumes(){
    try {
      const volumes=await api("/audit/unused-volumes");
      showOutput("Volumes sem uso aparente",
        volumes.length?volumes.map(v=>v.name+" ("+v.driver+")").join("\n"):
        "Nenhum volume sem referências de containers encontrado.");
    } catch(err){toast(err.message,true);}
  }
  async function loadMonitor(){
    const display=$("df-monitor-list"),events=$("df-monitor-events");
    display.textContent="Coletando dados do Docker...";
    try{
      const data=await api("/monitor/sample","POST",{limit:8});
      display.innerHTML='<table class="df-table"><thead><tr><th>Container</th><th>CPU</th><th>Memória</th><th>Rede RX / TX</th></tr></thead><tbody>'+
        data.samples.map(c=>'<tr><td><b>'+esc(c.name)+'</b></td><td>'+
          (c.error?esc(c.error):esc(c.current.cpu_percent)+"%")+'</td><td>'+
          (c.error?"—":(c.current.memory_bytes/1048576).toFixed(1)+" MiB / "+
           (c.current.memory_limit/1048576).toFixed(0)+" MiB")+'</td><td>'+
          (c.error?"—":(c.current.network_rx/1048576).toFixed(2)+" / "+
           (c.current.network_tx/1048576).toFixed(2)+" MiB")+'</td></tr>').join("")+
        '</tbody></table>'+(data.samples.length?"":'<div class="df-empty">Nenhum container em execução.</div>');
    }catch(err){display.textContent=err.message;}
    try{
      const list=await api("/monitor/events");
      events.innerHTML='<table class="df-table"><thead><tr><th>Horário (Unix)</th><th>Tipo</th><th>Ação</th><th>Recurso</th></tr></thead><tbody>'+
        list.reverse().map(e=>'<tr><td>'+esc(e.time)+'</td><td>'+esc(e.type)+'</td><td>'+
          esc(e.action)+'</td><td>'+esc(e.actor)+'</td></tr>').join("")+'</tbody></table>';
    }catch(err){events.textContent=err.message;}
  }
  async function loadTasks(){
    try{
      const jobs=await api("/tasks");
      $("df-task-list").innerHTML='<table class="df-table"><thead><tr><th>Operação</th><th>Estado</th><th>Início</th><th>Ações</th></tr></thead><tbody>'+
       jobs.map(j=>'<tr><td>'+esc(j.label)+'</td><td>'+esc(j.state)+'</td><td>'+esc(j.created)+'</td><td>'+
        (j.state==="queued"?rowButton("task-cancel","Cancelar",j.id):"—")+'</td></tr>').join("")+
       '</tbody></table>'+(jobs.length?"":'<div class="df-empty">Nenhuma tarefa registrada.</div>');
    }catch(err){$("df-task-list").textContent=err.message;}
  }
  async function loadNetworks(){
    try{
      const networks=await api("/networks");app.networks=networks;
      $("df-network-list").innerHTML='<table class="df-table"><thead><tr><th>Rede</th><th>Driver / IPAM</th><th>Containers</th><th>Ações</th></tr></thead><tbody>'+
        networks.map(n=>'<tr><td><b>'+esc(n.name)+'</b><small>'+esc(n.id.slice(0,12))+'</small></td>'+
         '<td>'+esc(n.driver)+'<small>'+esc(JSON.stringify(n.ipam?.Config||[]))+'</small></td>'+
         '<td>'+esc((n.containers||[]).map(x=>x.name).join(", ")||"—")+'</td><td><div class="df-row-actions">'+
         rowButton("network-connect","Conectar",n.id)+
         (!["bridge","host","none"].includes(n.name)?rowButton("network-remove","Remover",n.id,"danger"):"")+
         '</div></td></tr>').join("")+'</tbody></table>';
    }catch(err){$("df-network-list").textContent=err.message;}
  }
  async function createNetwork(){
    const data=await ask({title:"Rede bridge com IPAM",description:"Subnet e gateway são opcionais. Revise antes de criar no Docker.",
      fields:[{key:"name",label:"Nome",value:"rede-lab"},
              {key:"subnet",label:"Sub-rede CIDR (opcional)",value:""},
              {key:"gateway",label:"Gateway (opcional)",value:""},
              {key:"internal",label:"Isolada? 1=sim; 0=não",value:"0"}],confirmText:"Criar"});
    if(!data)return;
    try{await api("/networks/action","POST",{action:"create",name:data.name,
      subnet:data.subnet,gateway:data.gateway,internal:data.internal==="1"});
      toast("Rede criada");await loadNetworks();}
    catch(err){toast(err.message,true);}
  }
  async function networkAction(action,id){
    const n=app.networks.find(item=>item.id===id);
    if(!n)return;
    try{
      if(action==="network-remove"){
        if(!(await confirmed("Excluir rede?","A rede não pode conter containers ligados.","Excluir")))return;
        await api("/networks/action","POST",{action:"remove",network:id});
      }else{
        const data=await ask({title:"Conectar container à rede "+n.name,
          fields:[{key:"container",label:"Nome ou ID do container",value:""},
                  {key:"ipv4_address",label:"IPv4 fixo (opcional)",value:""}],confirmText:"Conectar"});
        if(!data)return;
        await api("/networks/action","POST",{action:"connect",network:id,
          container:data.container,ipv4_address:data.ipv4_address});
      }
      toast("Rede atualizada");await loadNetworks();
    }catch(err){toast(err.message,true);}
  }
  async function loadVolumes(){
    try{
      const list=await api("/volumes");
      $("df-volume-list").innerHTML='<table class="df-table"><thead><tr><th>Nome</th><th>Driver</th><th>Ação</th></tr></thead><tbody>'+
        list.map(v=>'<tr><td><b>'+esc(v.name)+'</b></td><td>'+esc(v.driver)+'</td><td>'+
          rowButton("volume-remove","Remover",v.name,"danger")+'</td></tr>').join("")+
        '</tbody></table>'+(list.length?"":'<div class="df-empty">Nenhum volume local.</div>');
    }catch(err){$("df-volume-list").innerHTML='<div class="df-empty">'+esc(err.message)+'</div>';}
  }
  async function newVolume(){
    const f=await ask({title:"Novo volume",fields:[{key:"name",label:"Nome do volume",value:"dados-app"}]});
    if(!f)return;
    try{await api("/volumes/action","POST",{action:"create",name:f.name});
      toast("Volume criado");await refresh();}
    catch(err){toast(err.message,true);}
  }
  async function removeVolume(name){
    if(!(await confirmed("Excluir volume?","ATENÇÃO: os dados persistidos podem ser perdidos. Containers em uso impedem remoção.","Excluir")))return;
    try{await api("/volumes/action","POST",{action:"remove",name});toast("Volume excluído");await refresh();}
    catch(err){toast(err.message,true);}
  }
  async function listProjects(){
    try {
      const data=await api("/compose/projects");
      $("df-project-list").innerHTML='<option value="">Selecione um projeto</option>'+
        data.map(n=>'<option value="'+esc(n)+'">'+esc(n)+'</option>').join("");
    }catch(err){toast(err.message,true);}
  }
  async function composeAction(action){
    const name=$("df-project").value.trim(),content=$("df-yaml").value;
    if(action==="down"&&!(await confirmed("Remover pilha Compose?",
      "docker compose down interrompe os serviços do projeto "+name+". Volumes não serão removidos.","Executar down")))return;
    if(action==="up"&&!(await confirmed("Executar Compose?",
      "O Docker irá criar / atualizar serviços e redes definidos no YAML. Revise o conteúdo antes de executar.","Executar up")))return;
    const output=$("df-compose-output");output.textContent="Executando docker compose "+action+"...";
    try{
      const result=action==="save"?
        await api("/compose/save","POST",{name,content}):
        await api("/compose/run","POST",{name,content,action});
      output.textContent=result.output||result.file||"YAML validado com sucesso.";
      if(!result.ok)toast("Compose retornou código "+result.code,true);
      else toast("Compose: "+action+" concluído");
      if(result.ok)listProjects();refresh();
    }catch(err){output.textContent="Erro: "+err.message;toast(err.message,true);}
  }
  async function loadProject(){
    const name=$("df-project-list").value;
    if(!name)return toast("Selecione um projeto salvo",true);
    try{const result=await api("/compose/load","POST",{name});
      $("df-project").value=name;setYaml(result.content);
      $("df-dockerfile").value=result.dockerfile||"";toast("Projeto carregado");}
    catch(err){toast(err.message,true);}
  }

  // --------------------------------------------------------
  // Editor duplo: Compose e Dockerfile, sem dependência de CDN.
  // --------------------------------------------------------
  const snippets = {
    python: 'FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD ["python", "app.py"]\n',
    node: 'FROM node:22-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci --omit=dev\nCOPY . .\nEXPOSE 3000\nCMD ["node", "server.js"]\n',
    nginx: 'FROM nginx:alpine\nCOPY ./dist /usr/share/nginx/html\nEXPOSE 80\n',
    go: 'FROM golang:1.24-alpine AS build\nWORKDIR /app\nCOPY . .\nRUN go build -o /server .\nFROM alpine:latest\nCOPY --from=build /server /server\nCMD ["/server"]\n',
    postgres: 'FROM postgres:16-alpine\nENV POSTGRES_DB=mydb\nEXPOSE 5432\n'
  };
  function switchEditor(mode) {
    app.editorMode = mode === "dockerfile" ? "dockerfile" : "compose";
    const dockerfile = app.editorMode === "dockerfile";
    $("df-yaml").hidden=dockerfile;
    $("df-dockerfile").hidden=!dockerfile;
    $("df-editor-mode").textContent=dockerfile?"DOCKERFILE · UTF-8":"YAML · UTF-8";
    document.querySelectorAll("[data-editor]").forEach(el=>
      el.classList.toggle("active",el.dataset.editor===app.editorMode));
    document.querySelectorAll(".df-dockerfile-actions").forEach(el=>el.hidden=!dockerfile);
    document.querySelectorAll(".df-compose-action").forEach(el=>el.hidden=dockerfile);
  }
  async function saveDockerfile() {
    const name=$("df-project").value.trim(),content=$("df-dockerfile").value;
    const result=await api("/compose/dockerfile","POST",{name,content});
    toast("Dockerfile salvo no workspace local");
    return result.folder;
  }
  async function buildDockerfile() {
    const tag=$("df-dockerfile-tag").value.trim();
    if(!tag)return toast("Informe uma tag para a imagem",true);
    if(!(await confirmed("Construir imagem?",
      "O Dockerfile será salvo e executado com o contexto isolado deste projeto. COPY precisa de arquivos que já estejam neste workspace.",
      "Iniciar build")))return;
    try {
      $("df-compose-output").textContent="Build: "+tag+"...";
      const folder=await saveDockerfile();
      const result=await api("/images/action","POST",{action:"build",path:folder,tag});
      $("df-compose-output").textContent=result.log||"Imagem criada: "+result.id;
      toast("Imagem Docker criada");refresh();
    } catch(err) {
      $("df-compose-output").textContent="Falha: "+err.message;
      toast(err.message,true);
    }
  }

  async function refreshTerminalList(){
    try{
      const containers=await api("/containers");
      const running=containers.filter(c=>c.status==="running");
      const select=$("df-terminal-container"),old=select.value;
      select.innerHTML=running.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join("");
      if(running.some(c=>c.id===old))select.value=old;
    }catch(err){toast(err.message,true);}
  }
  function terminalText(s){
    // Suporte a shell e comandos line-oriented; sem prometer emulação xterm completa.
    return String(s).replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g,"")
      .replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g,"").replace(/\r(?!\n)/g,"\n");
  }
  async function pollTerminal(){
    if(!app.terminal)return;
    try{
      const result=await api("/terminal/poll","POST",{session:app.terminal});
      const pre=$("df-terminal-output");
      if(result.output){pre.textContent=(pre.textContent+terminalText(result.output)).slice(-85000);
        pre.scrollTop=pre.scrollHeight;}
      if(!result.alive){clearInterval(app.pollTimer);app.pollTimer=null;
        app.terminal=null;$("df-terminal-input").disabled=true;
        $("df-terminal-state").textContent="sessão encerrada";}
    }catch(err){
      clearInterval(app.pollTimer);app.pollTimer=null;app.terminal=null;
      $("df-terminal-input").disabled=true;$("df-terminal-state").textContent=err.message;
    }
  }
  async function openTerminal(id){
    navigate("terminal");
    if(id) {
      await refreshTerminalList();
      $("df-terminal-container").value=id;
    }
    if(app.terminal) await closeTerminal();
    try {
      const selected=$("df-terminal-container").value;
      if(!selected)throw Error("Nenhum container em execução.");
      const result=await api("/terminal/open","POST",
        {id:selected,shell:$("df-terminal-shell").value});
      app.terminal=result.session;
      $("df-terminal-output").textContent="";$("df-terminal-input").disabled=false;
      $("df-terminal-input").value="";$("df-terminal-input").focus();
      $("df-terminal-state").textContent="PTY ativo";app.pollTimer=setInterval(pollTerminal,320);
    }catch(err){toast(err.message,true);}
  }
  async function closeTerminal(){
    const sid=app.terminal;
    if(app.pollTimer)clearInterval(app.pollTimer);
    app.pollTimer=null;app.terminal=null;
    $("df-terminal-input").disabled=true;
    $("df-terminal-state").textContent="sem sessão";
    if(sid)try{await api("/terminal/close","POST",{session:sid});}
    catch(err){toast(err.message,true);}
  }
  function bind(){
    document.querySelectorAll("[data-page]").forEach(el=>el.addEventListener("click",()=>navigate(el.dataset.page)));
    document.querySelectorAll("[data-nav]").forEach(el=>el.addEventListener("click",()=>navigate(el.dataset.nav)));
    $("df-refresh").onclick=refresh;
    $("df-new-container").onclick=createContainer;
    $("df-image-pull").onclick=pullImage;
    $("df-volume-new").onclick=newVolume;
    $("df-network-create").onclick=createNetwork;
    $("df-task-refresh").onclick=loadTasks;
    $("df-audit-refresh").onclick=loadAudit;
    $("df-log-refresh").onclick=fetchLogs;
    $("df-log-filter").oninput=filterLogs;
    $("df-log-download").onclick=exportLogs;
    $("df-image-clean").onclick=imageCleanup;
    $("df-volume-orphans").onclick=scanUnusedVolumes;
    $("df-monitor-refresh").onclick=loadMonitor;
    $("df-monitor-storage").onclick=async()=>{
      try{const result=await api("/diagnostics/storage");showOutput("Docker: uso de disco",JSON.stringify(result,null,2));}
      catch(err){toast(err.message,true);}
    };
    $("df-network-list").addEventListener("click",e=>{
      const button=e.target.closest("[data-action]");
      if(button)networkAction(button.dataset.action,button.dataset.id);
    });
    $("df-task-list").addEventListener("click",async e=>{
      const button=e.target.closest('[data-action="task-cancel"]');
      if(!button)return;
      try{await api("/tasks/cancel","POST",{id:button.dataset.id});await loadTasks();}
      catch(err){toast(err.message,true);}
    });
    $("df-ide-to-graph").onclick=async()=>{
      try{
        const graph=await api("/graph/from-compose","POST",{content:$("df-yaml").value});
        app.graph.loadGraph(graph);navigate("graph");toast("Compose convertido em rascunho visual; valide antes de executar.");
      }catch(err){toast(err.message,true);}
    };
    $("df-container-list").addEventListener("click",e=>{
      const btn=e.target.closest("[data-action]");if(btn)containerAction(btn.dataset.action,btn.dataset.id);
    });
    $("df-image-list").addEventListener("click",e=>{
      const btn=e.target.closest("[data-action]");
      if(!btn)return;
      if(btn.dataset.action==="image-remove")removeImage(btn.dataset.id);
      if(btn.dataset.action==="image-history"){
        api("/images/action","POST",{action:"history",image:btn.dataset.id})
          .then(data=>showOutput("Camadas (sem comandos de build)",JSON.stringify(data,null,2)))
          .catch(err=>toast(err.message,true));
      }
      if(btn.dataset.action==="image-tag")(async()=>{
        const values=await ask({title:"Criar tag",fields:[
          {key:"repository",label:"Repositório",value:"minha-imagem"},
          {key:"tag",label:"Tag",value:"dev"}],confirmText:"Criar"});
        if(!values)return;
        try {
          await api("/images/action","POST",{action:"tag",image:btn.dataset.id,...values});
          toast("Tag criada");await loadImages();
        } catch(err){toast(err.message,true);}
      })();
    });
    $("df-volume-list").addEventListener("click",e=>{
      const btn=e.target.closest("[data-action]");if(btn&&btn.dataset.action==="volume-remove")removeVolume(btn.dataset.id);
    });
    $("df-compose-validate").onclick=()=>composeAction("validate");
    $("df-compose-up").onclick=()=>composeAction("up");
    $("df-compose-down").onclick=()=>composeAction("down");
    $("df-compose-save").onclick=()=>composeAction("save");
    $("df-compose-load").onclick=loadProject;

    // O seletor e os comandos de arquivo acompanham a aba ativa.
    document.querySelectorAll("[data-editor]").forEach(el=>
      el.addEventListener("click",()=>switchEditor(el.dataset.editor)));
    $("df-dockerfile-template").onclick=async()=>{
      const name=$("df-dockerfile-snippet").value;
      if($("df-dockerfile").value.trim() &&
        !(await confirmed("Substituir Dockerfile?",
          "O conteúdo atual será substituído pelo template selecionado.","Substituir")))return;
      $("df-dockerfile").value=snippets[name]||"";
      toast("Template inserido: "+name);
    };
    $("df-dockerfile-save").onclick=async()=>{
      try{await saveDockerfile();}catch(err){toast(err.message,true);}
    };
    $("df-dockerfile-build").onclick=buildDockerfile;
    $("df-ide-open").onclick=()=>$("df-ide-file").click();
    $("df-ide-file").onchange=async e=>{
      const file=e.target.files[0];
      if(file){
        const editor=app.editorMode==="dockerfile"?$("df-dockerfile"):$("df-yaml");
        editor.value=await file.text();
        toast(file.name+" importado para o editor");
      }
      e.target.value="";
    };
    $("df-ide-export").onclick=()=>{
      const dockerfile=app.editorMode==="dockerfile";
      download(dockerfile?"Dockerfile":"docker-compose.yml",
        $(dockerfile?"df-dockerfile":"df-yaml").value,dockerfile?"text/plain":"text/yaml");
    };
    [$("df-yaml"),$("df-dockerfile")].forEach(editor=>{
      editor.addEventListener("keydown",e=>{
        if(e.key==="Tab"){
          e.preventDefault();
          e.target.setRangeText("  ",e.target.selectionStart,e.target.selectionEnd,"end");
        }
        if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s"){
          e.preventDefault();
          if(app.editorMode==="dockerfile")saveDockerfile().catch(err=>toast(err.message,true));
          else composeAction("save");
        }
      });
    });
    $("df-terminal-open").onclick=()=>openTerminal();
    $("df-terminal-close").onclick=closeTerminal;
    $("df-terminal-input").addEventListener("keydown",async e=>{
      if(!app.terminal)return;
      if(e.ctrlKey&&e.key.toLowerCase()==="c"){
        e.preventDefault();await api("/terminal/send","POST",{session:app.terminal,input:"\u0003"});return;
      }
      if(e.key==="Enter"&&!e.shiftKey){
        e.preventDefault();const value=e.target.value;e.target.value="";
        try{await api("/terminal/send","POST",{session:app.terminal,input:value+"\n"});}
        catch(err){toast(err.message,true);}
      }
    });
  }
  async function mount(){
    if(app.mounted)return;
    if(!$("dockerflow-root"))return;
    app.mounted=true;bind();navigate("graph");
    app.graph=window.DockerGraph({api,toast,ask,setYaml,navigate,refresh,download,openTerminal,showOutput});
    await refresh();
    if(app.overview.online){
      try{await app.graph.importDocker(true);}
      catch(err){toast("Falha ao importar topologia: "+err.message,true);}
    }
  }
  function dispose(){
    app.mounted=false;
    if(app.pollTimer)clearInterval(app.pollTimer);
    app.pollTimer=null;
    if(app.terminal)api("/terminal/close","POST",{session:app.terminal}).catch(()=>{});
    app.terminal=null;
  }
  window.DockerFlow={mount,dispose,api};
})();
