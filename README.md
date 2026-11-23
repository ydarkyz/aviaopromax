# aviaopromax

Monitor de promoções de passagens aéreas. Busca as tarifas mais baratas a partir
de uma origem para **qualquer destino** em **datas flexíveis**, guarda o histórico
e avisa quando aparece promoção.

Datas e destinos são opcionais: deixe vazios até decidir.

Por padrão busca **somente voos diretos** (`direct_only = true`).

## Interface web

```bash
python -m aviaopromax.web
```

Abre `http://localhost:8000` no navegador: formulário de busca (origem, destinos,
meses, limites de alerta, só diretos, só ida), tabela com as tarifas mais baratas
por destino, promoções destacadas e botão para salvar a configuração em `config.toml`.
Sem token, marque "Modo teste" para ver dados falsos.

- **Aeroportos:** digite cidade, nome ou código e escolha na lista. Só aparecem
  aeroportos reais com voos comerciais regulares (base pública OurAirports,
  em `aviaopromax/static/airports.json`; para atualizar, veja `tools/build_airports.py`).
- **Datas:** "Datas exatas" com calendário (ida e volta, um dia ou um intervalo)
  ou "Meses flexíveis".

## Linha de comando

```bash
cp config.example.toml config.toml   # ajuste origem, limites etc.
python -m aviaopromax --mock         # teste com dados falsos
```

Com dados reais (token gratuito em https://www.travelpayouts.com/developers/api):

```bash
export TRAVELPAYOUTS_TOKEN=seu_token   # ou cole o token na própria interface web
python -m aviaopromax
```

## Fontes de preço (todas grátis)

- **Travelpayouts / Aviasales** (token obrigatório): busca para qualquer destino e
  meses inteiros. Só tem preços que outras pessoas pesquisaram nos últimos dias,
  então rotas pouco procuradas podem vir vazias.
- **SerpApi / Google Flights** (chave opcional, 250 buscas/mês): preço ao vivo.
  Usado só com destinos e datas exatas; no máximo 10 buscas por pesquisa.
- Quando um destino escolhido não tem preço, a interface mostra um link direto
  para a mesma busca no Google Flights.

As chaves podem ser coladas na interface (ficam em `config.toml`, que não vai
para o git) ou definidas em `TRAVELPAYOUTS_TOKEN` / `SERPAPI_KEY`.

## Alertas

- `alerts.max_price`: qualquer rota abaixo desse valor.
- `alerts.drop_pct`: rota que caiu X% abaixo do menor preço já visto (histórico em `prices.db`).
- Telegram opcional via `[telegram]` ou `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`.

Para rodar periodicamente, use cron, por exemplo a cada 6h:

```
0 */6 * * * cd /caminho/aviaopromax && python -m aviaopromax
```

## Pendências

- [ ] Confirmar origem (BOS?)
- [ ] Definir destinos
- [ ] Definir datas/meses
