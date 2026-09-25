# DockerFlow — Docker Studio em Vela

**DockerFlow 0.2** é uma ferramenta desktop para visualizar e administrar Docker e desenhar suas redes com blocos, inspirada na interação de editores visuais como o BRModelo. Foi migrada de PyQt6 + gRPC para o **Vela Framework 0.2.2**, mantendo uma IDE para Docker Compose e Dockerfile e acrescentando um terminal Docker integrado.

> **Status:** a migração Vela da PR #2 está integrada à `main`. A continuação (tema escuro, editor avançado e diagnósticos) está na PR #3 até validação de testes e aceitação manual. Não use a aplicação experimental em hosts de produção sem revisar cada operação.

## Recursos

- **Laboratório visual:** importe containers/redes existentes, arraste novos blocos, dê zoom, edite rascunhos e conecte containers a redes bridge. Clicar no conector de dois containers propõe uma rede compartilhada.
- **Operações em estágios:** o canvas é somente um desenho até clicar **Aplicar alterações** e confirmar; geração de **Compose** a partir dos nós e conexões, export/import JSON, exemplo offline.
- **Visão geral e gerenciamento:** containers (iniciar/parar/reiniciar/pausar/remover, inspecionar, logs, stats), imagens (pull/build/remove) e volumes (listar/criar/remover).
- **IDE:** editor Compose, validação, `up -d`, `down`, gerenciamento de projetos locais; editor Dockerfile, presets Python/Node/Nginx/Go/PostgreSQL e build local.
- **Terminal no aplicativo:** PTY Docker real para comandos e shells `sh`, `bash`, `ash`, com histórico de comandos só na memória da sessão (não salvo). **Não** é emulador full-screen xterm.
- **PR #3, experimental:** alternância tema sistema/claro/escuro persistente; canvas com seleção múltipla, cópia/duplicação só de rascunhos, encaixe à grade, pesquisa, layout e PNG; IPAM IPv6/aliases/DNS; diagnóstico DNS/TCP/HTTP entre containers; identificação de volumes referenciados inclusive por containers parados; listagem de processos sem argumentos; IDE com números de linha e prévia sintática offline.
- **Segurança da topologia:** novos containers do desenho entram diretamente na primeira rede ligada, sem anexação implícita à bridge padrão; blocos sem rede explícita usam `network=none`. O pré-voo permanece consultivo: alterações podem ocorrer entre validação e execução e a aplicação ainda não tem rollback atômico.

Interface independente das páginas visuais do shell Vela: HTML/CSS/JS offline na janela nativa, tema editorial branco/verde e API Python em loopback. O código antigo gRPC e PyQt6 foi preservado no repositório para comparação, **não é executado** no novo `manage.py`.

## Desenvolvimento (Linux Mint/Ubuntu)

Requer Python 3.12, Docker Engine funcional e Qt6/WebEngine. Execute o Docker com um usuário autorizado. Acesso ao socket do Docker equivale a controle privilegiado sobre o host: não exponha a API Vela na rede.

~~~bash
git clone https://github.com/zxlawdx/Docker-Manager.git
cd Docker-Manager
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements-build.txt
python manage.py collectstatic --no-tailwind
python manage.py runapp
~~~

Para instalar dependências de Qt6/WebEngine do sistema operacional, consulte o guia de distribuição do Vela. **Use venv isolado**, sem `--system-site-packages`, no build Qt6; isso evita dependências incompatíveis de `pkg_resources`, `jaraco` e GUI do Python do sistema. O aplicativo abre mesmo quando o Docker Engine estiver indisponível; operações no daemon exigem conexão.

## Testes e build

~~~bash
python -m unittest discover -s tests -v
node --check apps/dockerflow/static/js/graph.js
node --check apps/dockerflow/static/js/studio.js
python manage.py buildapp --gui qt6 --installer
./dist/DockerFlow/DockerFlow --self-test
~~~

No Windows, o comando de build também é `python manage.py buildapp --gui qt6 --installer`; o teste do binário é `.\dist\DockerFlow\DockerFlow.exe --self-test`.

O workflow `.github/workflows/release.yml` usa a mesma estratégia de release do projeto `acess_manager`: valida PRs e, após merge, gera builds **Linux x86_64** e **Windows x86_64** para cada nova tag `v*`, verifica os executáveis, publica ZIPs, checksums SHA256 e GitHub Release. Também aceita execução manual para tag existente.

~~~bash
git checkout main
git pull --ff-only
git tag v0.2.0
git push origin v0.2.0
~~~

Só crie tags após revisar o PR e confirmar a execução do workflow.

## Estrutura nova

~~~text
apps/dockerflow/
  api.py                    # endpoints HTTP Vela locais
  services/
    docker_service.py       # adapter SDK Docker
    compose_service.py      # workspace local e docker compose
    graph_service.py        # grafo -> YAML
    terminal_service.py     # sessões PTY dentro de containers
  views/studio.py
  templates/studio.html
  static/css/studio.css
  static/js/{studio,graph}.js
config/{settings,wsgi}.py
tests/test_dockerflow.py
.github/workflows/release.yml
~~~

Consulte [auditoria técnica, limitações, comparativo do projeto original e roadmap](docs/DOCKER_GAP_ANALYSIS.md) para a lista completa. Alterações sequenciais do diagrama **não são atômicas**; se uma etapa falhar, atualize a topologia antes de tentar novamente.


## Desenvolvimento e escopo

Consulte o [roteiro completo de funcionalidades, pendências e limites](docs/ROADMAP_ALL.md). A migração Vela foi integrada na PR #2. A PR #3 amplia o editor e a infraestrutura; não considere os recursos experimentais liberados para produção antes de validar a aplicação nativa e os workflows.

## PR #3 · correções de arraste, visualização por redes e biblioteca YAML

O editor agora captura os movimentos no **stage** estável, em vez de no próprio cartão (que pode perder eventos do Qt WebView). Há duas formas de trabalhar no mesmo rascunho:

- **Grafo (linhas):** arraste os cartões; faça ligações pelos conectores.
- **Redes (áreas):** alterne para `Áreas (arrastar)` e solte um container dentro do quadrado da rede. Isso cria uma associação **pendente**, inclusive para containers já existentes; somente `Aplicar alterações` executa a ligação no Docker.

**Trazer todas as relações** consulta novamente containers e redes do daemon e reconstrói as associações observadas. A importação preserva identidades somente durante essa sessão; projetos salvos/JSON carregam sempre como rascunho. O botão pergunta antes de descartar alterações locais. Containers associados a várias redes ocupam visualmente a primeira e mostram etiquetas para as demais. Remover a associação deve ser explícito pelo inspetor do grafo, não basta arrastar o container para fora do quadrado.

A biblioteca offline possui modelos individuais e stacks YAML editáveis (PostgreSQL, MySQL, MariaDB, MongoDB, Redis, RabbitMQ, Grafana, Prometheus, Nginx, Caddy, WordPress, Ollama, Registry, Python/Node e stacks prontas). Na Compose IDE, selecione o template, confirme a substituição do editor e revise o YAML. **Templates não executam o Docker automaticamente.** Modelos com banco de dados exigem variáveis de ambiente reais: placeholders `\u0024{VAR:?Defina...}` nunca podem ser aplicados como senha literal pelo canvas.

### Admin: remoção total opcional no Linux

A tela **Administração** possui verificação prévia e um botão separado para remoção de todos os containers **locais**. Este recurso é intencionalmente restrito a Linux com socket `/var/run/docker.sock` e agente gráfico polkit/pkexec instalado. Use o aplicativo como usuário normal autorizado a consultar o Docker. A sequência é: verificar a lista, digitar exatamente `APAGAR TODOS`, confirmar a janela gráfica do **sistema operacional** (fora da WebView) e conferir novamente os containers. Nenhuma senha é recebida no HTML, nenhuma elevação silenciosa ocorre e não há fallback automático se a autorização falhar. A operação força a remoção de containers, mas **não apaga volumes nomeados**. Dados apenas na camada gravável dos containers podem se perder.

Esta ferramenta não constitui controle de acesso multiusuário. Qualquer conta que já tenha permissão de escrever no socket Docker dispõe potencialmente de privilégios equivalentes aos de root; não exponha a aplicação na rede. Confira o daemon e faça backup antes de operações destrutivas.

## Variáveis e senhas no DockerFlow · atualização da PR #3

Os templates Compose usam referências como:

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:?Defina GRAFANA_PASSWORD}
```

**Não substitua o texto depois de `:` pela senha.** Em `${VAR:?mensagem}`, o texto depois de `?` é a mensagem quando a variável está ausente, não seu valor.

Na **Compose IDE**, escolha o **Nome do projeto** e abra o quadro **Variáveis e senhas**. Informe `GRAFANA_PASSWORD` e digite sua senha no campo próprio; clique em **Salvar variável neste projeto**, depois **Validar YAML** e **docker compose up**. A senha é transmitida ao Docker Compose como variável de ambiente no momento da execução, não é inserida no YAML nem devolvida por APIs de listagem. O aplicativo grava os valores em um arquivo JSON privado no workspace (modo 0600 no Linux, diretório 0700), **não em um keyring criptografado**: proteja sua conta e o backup do computador.

No **Laboratório visual**, selecione um container *planejado* e clique em **🔐 Definir senha deste serviço**. Informe a variável esperada pela imagem e a chave do projeto. O diagrama contém somente `${VARIAVEL}` e o backend resolve o valor do mesmo projeto ao criar o container, sem incluí-lo no JSON exportado. Para alterar credenciais de um container já existente, edite o Compose e **recrie** o serviço, conforme a imagem.

### Apagar todos os volumes

A tela **Administração** também possui uma opção independente para todos os volumes do Docker Engine local. O app lista os volumes (inclusive anônimos) e as referências encontradas; não permite executar caso **qualquer** volume esteja associado a um container existente, mesmo parado. Se desejar remover ambos, conclua primeiro a operação de containers, atualize a lista de volumes e só então digite `APAGAR VOLUMES` e autorize a janela nativa polkit. O botão não ignora erros nem possui modo silencioso. **Todo conteúdo dos volumes excluídos é irrecuperável sem backup**, inclusive dados de banco. Drivers externos podem afetar sistemas de armazenamento remotos.

### Arraste e alternativa acessível

Os eventos de movimento/soltura são capturados em nível de janela para lidar com perda de ponteiro na WebView Qt6. A paleta funciona por **arrastar ou clicar**; para mover um bloco, clique e arraste seu cartão. Se o dispositivo ainda não produzir arraste, selecione o bloco e use as **setas do teclado** (Shift+setas move 1 px). Em `Áreas (arrastar)`, soltar um container dentro de uma zona cria uma relação **pendente**: só o botão `Aplicar alterações` modifica o Docker.

O CI inclui um teste de interação que executa handlers de pointerdown/move/up, pan, zonas e referência de senhas sem Docker real. Ainda é necessária aceitação manual em Linux Mint com Qt6 e Windows.
