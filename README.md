# DockerFlow — Docker Studio em Vela

**DockerFlow 0.2** é uma ferramenta desktop para visualizar e administrar Docker e desenhar suas redes com blocos, inspirada na interação de editores visuais como o BRModelo. Foi migrada de PyQt6 + gRPC para o **Vela Framework 0.2.2**, mantendo uma IDE para Docker Compose e Dockerfile e acrescentando um terminal Docker integrado.

> **Branch de desenvolvimento:** `feat/vela-visual-studio`. A UI, os testes unitários e o pipeline foram adicionados, mas a integração com Docker Engine e os bundles de sistema devem passar por testes de aceitação antes de lançar uma versão final.

## Recursos

- **Laboratório visual:** importe containers/redes existentes, arraste novos blocos, dê zoom, edite rascunhos e conecte containers a redes bridge. Clicar no conector de dois containers propõe uma rede compartilhada.
- **Operações em estágios:** o canvas é somente um desenho até clicar **Aplicar alterações** e confirmar; geração de **Compose** a partir dos nós e conexões, export/import JSON, exemplo offline.
- **Visão geral e gerenciamento:** containers (iniciar/parar/reiniciar/pausar/remover, inspecionar, logs, stats), imagens (pull/build/remove) e volumes (listar/criar/remover).
- **IDE:** editor Compose, validação, `up -d`, `down`, gerenciamento de projetos locais; editor Dockerfile, presets Python/Node/Nginx/Go/PostgreSQL e build local.
- **Terminal no aplicativo:** PTY Docker real para comandos e shells `sh`, `bash`, `ash`. Compatível com comandos de linha; **não** é emulador full-screen xterm.

Interface independente das páginas visuais do shell Vela: HTML/CSS/JS offline na janela nativa, tema editorial branco/verde e API Python em loopback. O código antigo gRPC e PyQt6 foi preservado no repositório para comparação, **não é executado** no novo `manage.py`.

## Desenvolvimento (Linux Mint/Ubuntu)

Requer Python 3.12, Docker Engine funcional e Qt6/WebEngine. Execute o Docker com um usuário autorizado. Acesso ao socket do Docker equivale a controle privilegiado sobre o host: não exponha a API Vela na rede.

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
