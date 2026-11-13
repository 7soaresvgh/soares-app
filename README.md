# Soares Reserva AI — Heloysa Edition

Aplicação web de companhia/assistente com chat por IA, memória persistente, modo atividade manual e agente opcional para Windows detectar jogos em execução.

## O que está incluído
- Interface web responsiva em português, com paleta roxa, azul, lilás e verde.
- Cadastro e login com token JWT.
- Chat com histórico persistido.
- Memórias pessoais editáveis por meio da conversa (a IA pode sugerir salvar; o endpoint de memória também está disponível).
- Status de atividade: manual pelo site ou automático pelo agente Windows.
- Painel simples de status e endpoint para consultar se Soares está jogando.
- Backend FastAPI + SQLite por padrão.
- Integração OpenAI-compatible configurável por variáveis de ambiente.

## Requisitos
- Python 3.11+
- Navegador moderno
- Para respostas reais da IA: chave de API de um provedor compatível com a API Chat Completions.
- Opcional: Windows 10/11 para o agente de detecção de jogos.

## 1. Iniciar o backend

No terminal, dentro da pasta `backend`:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
# Edite .env e configure AI_API_KEY e JWT_SECRET
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abra `http://localhost:8000/docs` para ver a API.

Sem `AI_API_KEY`, o backend responde em modo de demonstração, avisando que a integração precisa ser configurada.

## 2. Abrir a interface web

Abra `frontend/index.html` no navegador. Para desenvolvimento, também pode servir a pasta com:

```bash
python -m http.server 5500 --directory frontend
```

Acesse `http://localhost:5500`. Se o backend estiver em outro endereço, ajuste `API_BASE` no início de `frontend/app.js`.

## 3. Criar as contas

Cadastre primeiro a conta de Heloysa no site. Cadastre sua conta separadamente. Configure `ADMIN_EMAIL` no `.env` com o e-mail que deve receber a permissão de administrador. A permissão é atribuída no próximo cadastro desse e-mail; para instalação local, o primeiro usuário também recebe papel admin.

**Importante:** não compartilhe a senha de administrador. Use HTTPS e um segredo JWT forte em produção.

## 4. Modo Atividade

### Manual
Entre no site e use o botão **Estou jogando / Encerrar atividade**. O status é atualizado imediatamente.

### Automático (Windows)
1. Cadastre/login no site e copie o token de acesso do navegador (DevTools → Application → Local Storage → `sra_token`) ou faça login via API.
2. Copie `windows-agent/config.example.json` para `config.json`.
3. Preencha `api_base`, `token` e a lista de processos.
4. Instale dependências e execute:

```bash
cd windows-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python agent.py
```

O agente verifica processos em intervalos configuráveis e atualiza o status. O token fica armazenado localmente no `config.json`; proteja esse arquivo. A detecção depende do nome do processo e pode exigir ajustes para cada jogo/launcher.

## 5. Colocar online

Para publicar:
- Hospede o backend em um serviço Python (Render, Railway, Fly.io ou VPS).
- Use PostgreSQL gerenciado ou mantenha SQLite apenas em VPS com disco persistente.
- Publique `frontend/` em hospedagem estática (Vercel, Netlify ou o mesmo domínio).
- Configure `CORS_ORIGINS` com o domínio exato do site.
- Configure `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` e `JWT_SECRET` no ambiente do servidor.
- Configure HTTPS. Nunca coloque a chave de IA no frontend.
- Configure backup do banco e limite de requisições no proxy.

O projeto vem pronto para rodar localmente; publicação exige criar as contas nos provedores de hospedagem e inserir as chaves privadas.

## Privacidade
A IA deve se apresentar como assistente virtual, não como Soares. Ela não envia mensagens em nome dele, não finge que ele respondeu e não promete que ele viu mensagens. O status de jogo é compartilhado apenas com contas autenticadas. Memórias podem ser apagadas pelo endpoint `DELETE /memories/{id}`. Para produção, revise consentimento, retenção e política de privacidade antes de convidar outras pessoas.
