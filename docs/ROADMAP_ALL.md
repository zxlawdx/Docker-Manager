# DockerFlow — implementação e backlog completo

**Data:** 24/09/2026. **Branches:** `main` inclui PR #2; PR #3 `feat/dark-mode-studio-plus` permanece experimental.

> Importante: funcionalidade presente em código não significa que tenha sido
> validada em todos os sistemas ou liberada para produção. Os itens abaixo são
> a visão de produto dos 100 recursos solicitados, além das extensões.

## Implementado na branch Vela

- [x] Vela desktop, design branco/verde personalizado, dashboard e Docker SDK local.
- [x] Gestão básica de containers, imagens, redes bridge e volumes.
- [x] Canvas de blocos e conexões por seleção, zoom, importação Docker e geração Compose.
- [x] Salvar/abrir diagramas, import/export JSON, export SVG, minimapa, undo/redo básico.
- [x] Templates iniciais de topologia: Web + DB, proxy + APIs, microsserviços.
- [x] Comparação do desenho com o Docker, baseada em nomes; não substitui reconciliação por IDs.
- [x] Conversão Compose→rascunho e rascunho→Compose com preservação inicial de campos originais.
- [x] IPv4 CIDR/gateway para redes bridge, IP fixo opcional ao conectar e diagnóstico básico por container.
- [x] Containers: portas TCP/UDP, CPU/memória, restart, read-only e no-new-privileges (backend).
- [x] Terminal PTY integrado básico e remoção sob demanda de sessões mortas/inativas.
- [x] Token de sessão e validação de host/origem da API local (não é RBAC).
- [x] Tarefas com pool limitado para pull/build/Compose e cancelamento de jobs enfileirados.
- [x] Métricas e eventos sob demanda, resumo de disco e relatório Markdown sem valores de env.
- [x] CI para unit tests, integração com Docker Engine e bundles Qt6 Linux/Windows por tag.

## P0 — estabilidade e segurança (1–12)

- [ ] Autorização granular quando multiusuário, keyring e tratamento de secrets.
- [x] Proteção inicial da API local por token, Host, Origin e Sec-Fetch-Site.
- [x] Operações longas básicas por jobs limitados.
- [ ] Jobs duráveis, streaming real, cancelamento seguro de jobs ativos e recuperação pós-crash.
- [ ] Rollback por ações compensatórias somente quando comprovadamente seguro.
- [ ] Reconciliação incrementada por Docker Events, identidade imutável e drift de configuração.
- [x] Reap de terminais expirados quando há abertura/consulta; [ ] limpeza periódica e limites de sessão.
- [ ] Padronização dos erros HTTP e dos códigos de domínio em todo o Vela.
- [ ] E2E da GUI, testes multiplataforma, importações adversariais e aceitação com Docker Desktop.
- [x] Persistência local validada e escrita atômica dos diagramas.
- [ ] Persistência de plano de operação, undo semanticamente separado de rollback, recuperação de crash.

## Canvas: itens 13–27 e novos blocos

- [x] Conexões por arraste no canvas; [ ] seleção múltipla, copiar/colar e duplicação.
- [x] Undo/redo de edições iniciais e minimapa básico.
- [ ] Snap-to-grid, alinhamento, agrupamento, layout automático, camadas e pesquisa visual.
- [x] Export SVG, [ ] PNG e PDF.
- [x] Projetos de diagrama e três templates iniciais; [ ] galeria extensível e versões históricas.
- [x] Comparação de topologia inicial; [ ] diff confiável por identidade e visualização rica.
- [ ] Tipos próprios: imagem, volume, porta, host, Compose, registry, secret, config,
      healthcheck, proxy, load balancer, banco de dados e serviço externo.
- [ ] Ligações tipadas, não misturar conexão de rede com dependência ou montagem.
- [x] Pré-visualização inicial read-only da aplicação (IDs, nomes, portas, ligações); [ ] planejamento completo de impactos, execução transacional e rollback de ações selecionadas.

## Network Lab: itens 28–41

- [x] Bridge com IPv4 CIDR/gateway e endereço fixo opcional.
- [ ] Suporte IPv6 completo, DNS customizado, aliases UI, múltiplas redes e rotas.
- [ ] Assistentes por driver: host, macvlan, ipvlan, overlay, none e plugins externos.
- [x] Diagnóstico básico de conectividade; [ ] verificação DNS/TCP/HTTP/ICMP
      com classificação comprovado/inferido/indisponível.
- [ ] Mapa de portas, inspeção completa de endpoints e histórico de associações.

## Containers: itens 42–58

- [x] Criação, imagem, portas TCP/UDP, mounts básicos, CPU/memória, restart e opções simples de segurança no backend, formulário e canvas.
- [ ] Formulário completo: healthchecks, env segura, mounts avançados, GPU/dispositivos,
      usuários, capabilities, logs, ulimits e recursos em lote.
- [ ] Processos internos, histórico de restart, comparação de configurações e perfis.
- [ ] Docker cp/export/commit, comandos favoritos, arquivos dentro de containers.

## IDE Compose/Dockerfile: itens 59–75

- [x] Editor texto inicial, Dockerfile presets e comandos Compose básicos.
- [x] Conversão bidirecional inicial de rascunho e Compose, com preservação parcial.
- [ ] Editor offline com numeração, highlighting, autocomplete, validação de schema,
      diagnósticos, formatação e editor de múltiplos arquivos.
- [ ] Explorer, Git, .dockerignore, diff, histórico, terminal de build e camadas.
- [ ] Roundtrip completo preservando âncoras, comentários e campos avançados.
- [ ] Profiles, secrets, configs, healthcheck, depends_on, múltiplos Compose e Compose Watch.
- [ ] BuildKit, Buildx Bake, multiarch, SBOM, cache, assinatura e proveniência.

## Terminal: itens 76–90

- [x] PTY básico integrado, sessões limitadas.
- [ ] xterm.js vendorizado offline, streaming WS autenticado, resize, vim/top,
      múltiplas abas e splits, busca, clipboard, temas e histórico opt-in.
- [ ] Reconexão, expiração proativa, gerenciador de sessões, arquivos, comandos favoritos,
      diversos containers e terminal do host isolado com permissão explícita.

## Observabilidade e logs

- [x] Estatísticas de CPU/memória/tráfego sob demanda e eventos recentes.
- [ ] Gráficos persistentes, I/O, uptime, healthchecks, alertas, Prometheus e incidentes.
- [x] Central inicial de snapshots de logs sob demanda com filtro textual e exportação; [ ] streams múltiplos, regex, pesquisa durável, timeline,
      exportação, presets e comparação de logs por conexão visual.

## Volumes, imagens e segurança: itens 91–100 e complementos

- [x] Listagem/criação/remoção de volumes e consulta inicial de uso de disco.
- [ ] Browser de volume, permissões, associação visual, volumes órfãos e histórico.
- [ ] Backup/restauração/agendamento/verificação/export; procedimentos consistentes
      especializados para PostgreSQL, MySQL etc. antes de prometer recuperação.
- [ ] Tags, camadas, histórico, comparação de imagens, prune guiado,
      import/export e credenciais seguras de registry.
- [ ] CVEs/SBOM, imagem obsoleta, privileged, socket montado, root,
      portas públicas, permissões de volumes, auditoria e RBAC.

## Infraestrutura, ideias e distribuição

- [ ] Docker Contexts, SSH/TLS, inventário multi-host, projetos por host/ambiente.
- [ ] Swarm/Kubernetes em plugins independentes e validação de recursos disponíveis.
- [ ] Architecture Time Machine, Docker Playground, Dependency Explorer, Deployment Preview,
      Resource Advisor, Troubleshooting Assistant e Chaos Lab explicitamente isolado.
- [ ] DockerFlow AI opcional/local com geração de rascunho e aprovação antes de executar.
- [ ] Verificação de updates, ARM64, macOS, integração Git, templates compartilháveis,
      API documentada/versionada, sistema de extensões, i18n e documentação interativa.
- [ ] Extensão opcional Docker Desktop, separada do aplicativo Vela.

## Critério de aceitação

Somente marque como concluído quando houver backend, interface utilizável,
validação de entradas, documentação, testes unitários/integrados relevantes
e teste manual da versão nativa na plataforma. Ausência de teste não pode
ser convertida em promessa de estabilidade.

### Atualizações adicionais

- [x] Auditoria heurística somente leitura de containers (privileged, socket, usuário, portas e capabilities), sem expor ENV.
- [x] Identificador de volumes não referenciados inclusive por containers parados; sem exclusão automática.
- [x] Histórico de camadas sem comandos de build, criação de tags e limpeza *dangling* somente mediante confirmação.
- [ ] Scanner CVE/SBOM, backups consistentes e recuperação de volumes continuam pendentes.

### Central de logs e revisão visual

- [x] Central de logs de containers com consulta sob demanda, filtro de texto e exportação TXT; ainda sem stream, armazenamento durável ou pesquisa regex.
- [x] Botão de pré-visualização do plano de execução antes de modificar o Docker.
- [x] Testes unitários adicionais para ocultação de instruções sensíveis do histórico de imagens, análise de prune e bindings iniciais da UI.

- [x] Campos básicos de CPU/memória/restart e mounts read-only/read-write expostos tanto no formulário quanto no inspetor visual de containers novos; faltam dispositivos, GPU e edição avançada de mounts.

## Continuação PR #3 — entregas incrementais (requerem aceitação visual)

- [x] Aparência claro, escuro e preferência do sistema, persistência local e contraste em todo o Vela Studio.
- [x] Canvas: Shift+seleção, cópia/duplicação em memória de nós de rascunho, conexões copiadas entre selecionados, snap de 20 px, organização automática, pesquisa visual e export PNG/SVG.
- [x] Rede bridge IPv4/IPv6 com IPAM, gateway separado, IPv6 estático, aliases e DNS customizado para novos containers.
- [x] Diagnóstico opt-in DNS/TCP/HTTP entre containers reais, sem invocar shell; resultado inconclusivo quando faltam ferramentas ou o protocolo não confirma sucesso.
- [x] Containers: consulta de processos sem COMMAND/ARGS; volumes associados a containers inclusive parados; inspeção de volume sem Options/labels para evitar revelar credenciais.
- [x] Canvas passa a criar containers diretamente na primeira rede desenhada. Sem arestas, usa network=none e exige resolver conflitos do pré-voo (inclusive publicação de porta sem rede).
- [x] IDE: linhas numeradas e prévia de realce sintático offline para YAML e Dockerfile, somente leitura, sem promessa de LSP/autocomplete.
- [x] Terminal: histórico volátil das últimas 50 entradas e atalhos de navegação; limpa o histórico ao desmontar a interface; não grava comandos em disco.
- [ ] Validação manual de acessibilidade, layouts WebView nativos Linux/Windows, restauração de sistema e testes de falha sob carga.

**Continua fora do escopo deste incremento:** rollback transacional, empregos persistentes/stream real, xterm.js/WS, parser YAML preservando comentários, armazenamento de segredos com keyring, edição multi-host, scanners CVE/SBOM, backup consistente e Kubernetes. Não usar marcações de conclusão para esses itens.

### Solicitações adicionais: arraste, redes como áreas, templates e administração

- [x] Corrigir arraste na WebView: eventos pointer capturados no stage estável.
- [x] Alternância entre grafo de linhas e zonas retangulares representando redes.
- [x] Arrastar container para uma zona cria uma aresta pendente; conexão real somente após pré-voo e confirmação.
- [x] Botão para importar todas as associações atualmente observadas no Docker Engine; múltiplas redes exibidas como etiquetas.
- [x] Biblioteca offline com 17 opções de serviços e stacks YAML; integração com a IDE e o canvas.
- [x] Admin Linux: prévia com identidade exata dos containers, frase destrutiva, revalidação e autorização polkit para remoção forçada via Docker CLI com socket explícito.
- [x] Testes unitários sobre catálogo, fluxo de admin, captura estática dos eventos e bindings da interface.
- [ ] Teste manual de arraste/soltar em WebView Linux e Windows com mouse/touchpad; ampliar cobertura automatizada E2E.
- [ ] Volumes de produção: backups consistentes por serviço, scanner de segurança, acesso multiusuário e migração entre daemons continuam pendentes.
