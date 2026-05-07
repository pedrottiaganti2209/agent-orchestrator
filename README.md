# Mainframe Migration Agents

Sistema de orquestração multi-agente para migração de aplicações COBOL/Mainframe para cloud Azure, utilizando LangGraph e a API da Anthropic.

## Visão Geral da Arquitetura

```
                   ┌──────────────────────────────────────────┐
                   │      MAINFRAME MIGRATION ORCHESTRATOR     │
                   │            (LangGraph Graph)              │
                   └──────────────────────────────────────────┘
                                        │
                                        ▼
                   ┌──────────────────────────────────────────┐
                   │          AGENTE DE ANÁLISE               │
                   │   Lê COBOL/JCL, extrai regras de negócio │
                   │   e gera specs BDD em Gherkin             │
                   └──────────────────────────────────────────┘
                           │                    │
               ┌───────────┘                    └───────────┐
               ▼                                            ▼
┌────────────────────────────┐          ┌────────────────────────────┐
│   AGENTE DE DESENVOLVIMENTO │          │   AGENTE DE DOCUMENTAÇÃO   │
│  Gera Java 17 + Spring Boot │          │  ADR, README, Confluence   │
│  + abre PR no GitHub        │          │                            │
└────────────────────────────┘          └────────────────────────────┘
               │                                            │
               └───────────────────────────────────────────┘
                                        │
                                        ▼
                   ┌──────────────────────────────────────────┐
                   │           AGENTE DE TESTES               │
                   │   JUnit 5 + Parity Tests vs Mainframe     │
                   └──────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │ Testes OK?                             │ Falhou (< 3x)?
                    ▼                                        ▼
   ┌───────────────────────────┐            ┌────────────────────────────┐
   │  AGENTE DE EMPACOTAMENTO  │            │  Retry → AGENTE DE         │
   │  Maven build + Docker     │            │  DESENVOLVIMENTO           │
   │  + Push ACR               │            │  (com contexto do erro)    │
   └───────────────────────────┘            └────────────────────────────┘
                    │
                    ▼
   ┌───────────────────────────┐
   │  AGENTE DE IMPLANTAÇÃO    │
   │  Deploy AKS + Rollback    │
   │  auto se error rate > 1%  │
   └───────────────────────────┘
                    │
                    ▼
   ┌───────────────────────────┐
   │  AGENTE DE OBSERVABILIDADE│
   │  Azure Monitor + Alertas  │
   │  + Workbooks              │
   └───────────────────────────┘
                    │
                    ▼
                 SUCESSO ✓
```

## Pré-requisitos

- Python 3.11+
- Docker Desktop
- Azure CLI autenticado (`az login`)
- Acesso ao Azure DevOps
- Conta na Anthropic com API Key
- Acesso ao GitHub com Personal Access Token

## Configuração do Ambiente

1. Clone o repositório:
```bash
git clone https://github.com/pedrottiaganti2209/agent-orchestrator.git
cd agent-orchestrator
```

2. Crie o ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com seus valores reais
```

## Executando uma Migração End-to-End

Exemplo com o programa `CALCJURO.cbl` (cálculo de juros compostos):

```bash
python examples/run_migration.py \
  --cobol examples/sample_cobol/CALCJURO.cbl \
  --jcl examples/sample_cobol/CALCJURO.jcl \
  --module-name CALCJURO
```

Acompanhe o progresso em tempo real nos logs estruturados (JSON) gerados no console.

## Agentes e Responsabilidades

| Agente | Arquivo | Responsabilidade |
|--------|---------|------------------|
| **AnalysisAgent** | `agents/analysis_agent.py` | Lê COBOL/JCL, extrai regras de negócio, gera specs BDD em Gherkin |
| **DocumentationAgent** | `agents/documentation_agent.py` | Gera ADR, README técnico e páginas Confluence |
| **DevelopmentAgent** | `agents/development_agent.py` | Converte COBOL → Java 17 + Spring Boot 3, abre PR no GitHub |
| **TestingAgent** | `agents/testing_agent.py` | Gera JUnit 5 + parity tests contra shadow do mainframe |
| **PackagingAgent** | `agents/packaging_agent.py` | Build Maven, Docker, push para Azure Container Registry |
| **DeploymentAgent** | `agents/deployment_agent.py` | Deploy no AKS com rollback automático se error rate > 1% |
| **ObservabilityAgent** | `agents/observability_agent.py` | Cria dashboards Azure Monitor, alertas e workbooks |

## Parity Testing com Shadow do Mainframe

O parity testing executa o mesmo input no mainframe (via shadow endpoint) e no novo serviço Java, comparando os outputs campo a campo com tolerância configurável.

Configure no `.env`:
```
MAINFRAME_SHADOW_ENDPOINT=https://mainframe-shadow.interno/api
MAINFRAME_SHADOW_API_KEY=sua_chave_aqui
PARITY_TOLERANCE=0.001
```

A comparação ignora timestamps e sequence numbers. Para campos financeiros, a tolerância padrão é 0.001 (configurável).

## Dashboards Azure Monitor

Após implantação bem-sucedida, o agente de observabilidade cria automaticamente:

- **Migration Progress Workbook**: Quantos módulos migrados com sucesso por semana
- **Parity Delta Dashboard**: Divergências entre mainframe e cloud em tempo real
- **SLA Dashboard**: Latência p99, error rate e disponibilidade por módulo
- **Custom Metric**: `parity_delta_count` para alertas automáticos

Acesse via: **Azure Portal → Monitor → Dashboards → "Migration Dashboard"**

## Estado e Histórico

- **Redis** (Azure Cache for Redis): estado ativo de execuções em andamento
- **Cosmos DB**: histórico auditável de todas as execuções com seus artefatos

Consulte histórico:
```python
from memory.cosmos_history import CosmosHistory
history = CosmosHistory()
execucoes = history.list_executions(module_name="CALCJURO")
```

## Troubleshooting

### "Parity delta acima do threshold"
- Verifique uso de `BigDecimal` no código Java (nunca `double` para finanças)
- Confira normalização de datas em `parity/comparator.py`
- Aumente `PARITY_TOLERANCE` temporariamente para diagnóstico

### "SonarQube quality gate failed"
- Execute `mvn sonar:sonar` localmente para ver detalhes
- Verifique cobertura mínima de 80%
- Corrija code smells críticos antes de nova tentativa

### "AKS deployment timeout"
- Verifique logs do pod: `kubectl logs -n migration <pod-name>`
- Confirme que o image pull secret está configurado
- Verifique resource limits do namespace

### Retry loop excedido (3 tentativas)
- O orquestrador registrou o failure no Cosmos DB com `status: FAILED`
- Acesse o histórico: Cosmos DB → container `migration-history` → filtrar por `execution_id`
- Corrija o problema manualmente e reinicie com o mesmo `execution_id`

## Estrutura do Repositório

```
mainframe-migration-agents/
├── orchestrator/          # Grafo LangGraph e estado compartilhado
├── agents/                # 7 agentes especializados
├── tools/                 # Integrações com GitHub, Azure, SonarQube etc.
├── prompts/               # System prompts para cada agente
├── memory/                # Redis (estado ativo) + Cosmos DB (histórico)
├── parity/                # Comparação campo a campo entre COBOL e Java
├── azure/                 # Pipelines, manifests Kubernetes e Bicep IaC
├── examples/              # CALCJURO.cbl e script de exemplo
└── tests/                 # Testes unitários e de integração
```

## Contribuindo

1. Crie branch a partir de `develop`: `git checkout -b feature/minha-feature`
2. Implemente com type hints completos e docstrings em português
3. Adicione testes unitários correspondentes (cobertura mínima 80%)
4. Abra PR com descrição clara do que foi alterado
5. Aguarde CI verde (SonarQube + pytest) antes do merge
