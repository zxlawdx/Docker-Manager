# DockerFlow 0.2 — auditoria técnica e roteiro

Auditoria realizada sobre o repositório original em `main` (commit `e9113dba6e35`, de 08/05/2026) e a proposta Vela da branch `feat/vela-visual-studio` (24/09/2026). Este documento separa recursos comprovados pela leitura do código de recursos recém-implementados **ainda sujeitos aos testes com um daemon Docker real e builds nativos**.

## 1. Estado do projeto original

| Subsistema | Como estava na versão PyQt6 + gRPC | Pontos de atenção confirmados |
| --- | --- | --- |
| Containers | Listar todos, iniciar e parar por RPC; formulário simples para criar containers | Cliente chama `RemoveContainer` que **não existe** no arquivo `.proto` nem no servidor. O formulário envia portas e volumes, porém o cliente gRPC básico só envia imagem/nome e o servidor só entende um `host:container` TCP, ignorando volumes. |
| Imagens | Listagem e dados aproximados de tamanho | Em `server.py`, `created_raw = created = ""` faz a data aparecer sempre vazia. Falta pull/delete/build por RPC. |
| IDE Docker | `create_container_page.py` já traz **Compose Builder + editor YAML + editor Dockerfile**; templates de imagens e snippets; execução por subprocesso | Deve ser preservada. Sua implementação estava ligada diretamente à UI PyQt e fragmentada em métodos da tela. |
| Terminal | `terminal_page.py` permite escolher container, shell e usuário | Abre terminal **externo do sistema**, via `QProcess`, em vez de uma sessão embutida na janela. |
| Arquitetura | Duas aplicações: desktop PyQt6 e servidor gRPC localhost:50051 | O Vela já tem servidor HTTP embutido e não precisa de um segundo backend para uso local. O antigo gRPC permanece no histórico, mas não é iniciado pela nova entrada Vela. **Risco identificado:** o servidor legado registra `add_insecure_port("[::]:50051")` apesar de exibir `localhost`, potencialmente expondo controle Docker a todas as interfaces sem TLS/autenticação se o firewall permitir. |
| Redes, volumes e visualização | Não existiam páginas ou contratos `.proto` para gerenciá-los | Não havia montagem de topologias, ligações de redes ou importação visual do estado Docker. |
| Distribuição | Python sem workflow de release no repositório | Não havia build nativo por tag, artefatos assinados por checksum nem release automatizada. |

## 2. Implementação na branch Vela

| Área | Implementado | Limitações honestas |
| --- | --- | --- |
| Interface | SPA Vela 0.2.2; design próprio branco, sálvia e verde-floresta; sidebar, painel, filtros visuais e responsividade | UI precisa de verificação manual em Linux/Windows e em várias resoluções. |
| Laboratório visual | Importa containers/rede **reais** do Docker, coloca blocos na tela; arrastar, zoom/pan; conecta rede ↔ container por botões circulares; conectar dois containers propõe criar uma rede `bridge`; edita propriedades do rascunho; exporta/importa JSON | Importação lê o estado no momento da consulta; **não** sincroniza continuamente eventos de rede ou múltiplos usuários. |
| Operações seguras | Desenho isolado da execução; botão **Aplicar alterações** exige confirmação e cria redes, containers e anexos nessa ordem; desfazer uma conexão real vira desconexão pendente | **Não** implementa transação/rollback. Se a terceira operação falhar, as duas primeiras podem já ter sido aplicadas. Atualize o grafo e revise o estado antes de repetir. |
| Geração de Compose | Converte nós e arestas para `services:` e `networks:`; redes reais importadas viram `external: true`; abre o YAML na IDE para revisão | Não exporta todas as configurações de um container existente (segredos, limites, healthcheck, mounts, portas etc.). É um **esqueleto editável**, não um clone completo. |
| Recursos Docker | Containers: list/create/start/stop/restart/pause/unpause/remove, inspect sem env, logs e stats; imagens: list/pull/build/remove; redes bridge: list/create/connect/disconnect/remove; volumes: list/create/remove | Não implementa `commit`, `tag`, prune seletivo, snapshots ou browsing de volumes. |
| IDE | Mantém editor Compose, validação e `up -d`/`down`; projetos salvos na pasta de dados do usuário; editor Dockerfile independente, templates Python/Node/Nginx/Go/Postgres, save/build | Editor é um textarea responsivo, não Monaco; YAML/Dockerfile ainda sem autocomplete, lint contextual avançado ou diff. O build de Dockerfile usa o contexto persistido do workspace; `COPY` de arquivos não salvos ali falhará. Para projeto completo, use build por diretório na tela de imagens. |
| Terminal | PTY Docker real **integrado**, com envio de comandos, retorno na própria UI, Ctrl-C, shells sh/bash/ash; sessões não dependem do terminal do SO | Renderizador de **linhas de texto**, não emulador xterm completo: `vim`, `top` e aplicações full-screen podem exibir incorretamente. Sem resize TTY/cópia de arquivos. |
| Build | Workflow inspirado em `acess_manager`: testes em PR; ao enviar tags `v*`, builds Qt6 Linux/Windows em ambientes Python isolados, testes `--self-test`, ZIP + SHA256 e GitHub Release | O CI executa testes unitários e um teste integrado em Docker Engine descartável (criar rede bridge, conectar dois containers, verificar e desconectar). **Builds de Linux e Windows também são verificados em PR**; a publicação do GitHub Release continua exclusiva de tags. Os testes não substituem a validação interativa com Docker Desktop/Engine em máquinas reais. |

### Por que a arquitetura mudou

Na edição Vela, o `VelaApp` assume janela, registro de páginas, assets e API HTTP. Um serviço Python usa o SDK Docker como **fonte de verdade**. O diagrama mantém estado em JavaScript separado do daemon; o endpoint só é chamado quando o usuário decide aplicar ou importar. A IDE compartilha o serviço Python, em vez de duplicar lógica na interface gráfica. Não se copia código visual nem a marca do BRModelo; reutilizam-se ideias de interação com blocos e ligações.

### Segurança e limites operacionais

- A API HTTP do Vela escuta somente `127.0.0.1`; **não** a exponha na LAN, em proxy, nem a execute como root. Acesso ao socket Docker normalmente equivale a privilégios elevados no host.
- A interface não mostra `Config.Env` completo no inspect. Entretanto, projetos Compose e variáveis definidas pelo usuário ainda podem conter credenciais; proteja os arquivos do workspace e prefira secrets externos para produção.
- Remover container exige que esteja parado; remover rede exige ausência de containers anexados; ações destrutivas pedem confirmação. As redes padrão (`bridge`, `host`, `none`) têm proteção para exclusão.
- Recursos Docker são executados no **host local**. Não há login remoto, troca de contexto nem gerenciamento multiusuário.
- Para produção, ainda é recomendável acrescentar proteção por token e validação de origem na API local sensível. Loopback, sozinho, não isola outros processos locais ou páginas com acesso ao localhost.

## 3. Lacunas prioritárias para novas versões

**Estabilidade:** testes E2E com Docker Engine real e containers descartáveis; snapshots e rollback antes de modificar topologia; observação de Docker Events para atualização incremental; reconciliação quando o Docker mudar fora do aplicativo; logs e terminal com limites e sessões expiradas; confirmação dos recursos legados antes de remover a pasta PyQt/gRPC.

**Experiência de edição:** seleção múltipla de blocos, copiar/colar, alinhar, atalhos, desfazer/refazer, minimapa, busca por rede e container, cores por ambiente, layout automático e persistência de diagramas por projeto; editor YAML/Dockerfile com lint, diff, autocomplete e syntax highlighting; xterm.js com stream de baixa latência, tamanho PTY negociado e WebSocket local autenticado.

**Docker avançado:** Docker contexts e SSH/TLS seguros para hosts remotos; registry login privado sem persistir credenciais em texto; tags, history, prune orientado e recuperação de espaço; mounts/bind, gestão de arquivos e backup de volumes; processos, eventos, métricas e gráficos históricos; perfis Compose, BuildKit/buildx e healthchecks; complementos opcionais para Swarm e Kubernetes em módulos independentes.

## 4. Executar na branch de desenvolvimento

Requisitos: Python 3.12, Docker Engine ativo e acesso autorizado do usuário ao socket Docker. Para UI Qt6 no Linux Mint, instale dependências do SO conforme a documentação do Vela. Recomenda-se um **venv isolado** — sem `--system-site-packages` — para evitar misturar setuptools/jaraco/Qt do host.

~~~bash
git clone -b feat/vela-visual-studio https://github.com/zxlawdx/Docker-Manager.git
cd Docker-Manager
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements-build.txt
python manage.py collectstatic --no-tailwind
python manage.py runapp
~~~

Para executar somente testes estáticos/unitários sem Docker:
~~~bash
python -m unittest discover -s tests -v
node --check apps/dockerflow/static/js/graph.js
node --check apps/dockerflow/static/js/studio.js
~~~

Build Qt6 nativo:
~~~bash
python manage.py buildapp --gui qt6 --installer
./dist/DockerFlow/DockerFlow --self-test
~~~

Windows: crie o venv normalmente e use `python manage.py runapp`; execute `dist\\DockerFlow\\DockerFlow.exe --self-test` após o build.

## 5. Tags e GitHub Actions

O workflow `.github/workflows/release.yml` roda testes e builds nativos para pull requests em `main`, mas publica release **apenas** em `push` de tags `v*` ou disparo manual para uma tag já existente. Ele não faz o upload do código para a branch principal nem publica automaticamente a branch feature.

Depois de revisar o PR, integrá-lo à `main` e confirmar todos os jobs de CI, o primeiro release pode ser gerado com:

~~~bash
git checkout main
git pull --ff-only
git tag v0.2.0
git push origin v0.2.0
~~~

Não crie a tag antes de revisar as validações em Linux e Windows. Os ZIPs publicados em Releases incluem arquivos `.sha256` para conferência da integridade.
