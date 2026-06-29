# Regras de Negócio — Projeto Next Level (Dashboard de Vendas)

## Coluna "Classe" — significado dos códigos encontrados

| Código | Classe                      | Uso no projeto                                   |
|--------|------------------------------|---------------------------------------------------|
| 2      | VE - VENDA                  | Base de faturamento e quantidade                  |
| 4      | DV - DEVOL. DE VENDA         | Subtrai do faturamento e da quantidade             |
| 5      | BO - SAÍDA BONIFICADA        | Soma na quantidade/peso, NÃO entra no faturamento  |
| 15     | DEV. DE BONIFICAÇÃO          | Subtrai da quantidade/peso, NÃO entra no faturamento |
| 31     | REMESSA FUTURA               | Apenas informativa (rastreio de estoque). NÃO entra em nenhum cálculo — a venda real já é lançada separadamente como Classe 2 |
| 39     | BRIN - SAÍDA BRINDES          | Informativa, fora de todos os cálculos |
| 11     | TR - TROCA MERCADORIA         | Informativa, fora de todos os cálculos (confirmado 29/06/2026) |
| 23     | TC - TRAB. CAMPO              | Informativa, fora de todos os cálculos (confirmado 29/06/2026) |
| 37     | SAIDA AMOSTRA GRATIS          | Informativa, fora de todos os cálculos (confirmado 29/06/2026) |
| 43     | SAID-NOME DA QUALY            | Informativa, fora de todos os cálculos (confirmado 29/06/2026) |

## VALIDAÇÃO REAL — Primeira execução completa do robô (29/06/2026)

Primeira execução de ponta a ponta via GitHub Actions, processando o arquivo
completo da planilha do Mês Vigente (20.998 linhas, 01/06/2026 a 26/06/2026,
SEM nenhum corte/truncamento). Resultado:
- Soma bruta de todas as linhas (sem filtro de Classe): R$ 6.696.938,99 —
  validado como IDÊNTICO (diferença R$ 0,00) ao cálculo manual de Fernando
  no Excel para o mesmo arquivo.
- Faturamento (Classe 2 + 4): R$ 5.981.944,74
- Quantidade ajustada: 102.012 unidades
- Peso líquido ajustado: 147.335,12 kg
- 64 RCAs distintos no período
Essa validação confirma que o pipeline (leitura via link publicado +
processamento + regras de negócio) está correto e funcionando de ponta a
ponta, sem os problemas de truncamento que afetavam a leitura via chat.

## Fórmulas oficiais

**Faturamento (R$):**
Faturamento = SOMA(Valor Total | Classe=2) + SOMA(Valor Total | Classe=4)

**Quantidade / Peso Líquido vendido:**
Qtd/Peso = SOMA(Qtd ou Peso | Classe IN {2, 4, 5, 15})

⚠️ CORREÇÃO IMPORTANTE (registrada em 26/06/2026, durante construção do
script): o sistema de origem já grava Devolução de Venda (Classe 4) e
Devolução de Bonificação (Classe 15) com VALOR NEGATIVO nativamente
(ex: devolução de R$100 já aparece como -100,00, e quantidade -1 também).
A primeira versão do script aplicava uma inversão de sinal manual
(Venda=+1, Devolução=-1) por cima desse valor já negativo — um erro de
sinal duplo que transformava devoluções em positivas, INFLANDO o
faturamento em vez de reduzi-lo. Corrigido: agora o script apenas SOMA
os valores com o sinal nativo, sem nenhuma inversão. Validado manualmente
com amostra de teste (resultado: -259,67, batendo com o cálculo feito à
mão). O resultado anterior de R$ 391.378,79 (calculado com a amostra
truncada do Drive) estava incorreto por esse motivo e deve ser ignorado.

## Observações de qualidade de dados

- O CSV de origem está com encoding incorreto (caracteres acentuados corrompidos, ex: "Emiss o" em vez de "Emissão"). Precisa correção de encoding (provavelmente Latin-1/Windows-1252 → UTF-8) no pipeline de processamento.
- Separador de colunas: ponto e vírgula (;)
- Separador decimal: vírgula (ex: -104,85)
- Granularidade: 1 linha = 1 item de produto dentro de 1 nota fiscal (não 1 linha por venda/nota inteira)
- Coluna "RCA" = nome do vendedor/representante comercial (campo principal para agregação por vendedor)
- Coluna "Vendedor" (separada de RCA) está sempre vazia no relatório — DESCARTAR. Usar somente "RCA".
- Total de vendedores (RCA) distintos encontrados na amostra de Jun/26: 37

## Colunas selecionadas para o dashboard (em definição)

**Datas:** somente "Data Emissão" (descartar Saída, Fechamento, Canhoto, Pedido)

**Cliente:** Código Cliente/Fornecedor, Cliente/Fornecedor (razão social), Nome Fantasia
- PENDENTE: "Grupo Econômico" — não existe nas 88 colunas atuais. Será incluído depois via outra tabela dimensão (a confirmar fonte).

**Valor financeiro (Faturamento):** usar coluna "Valor Total" (valor do item/linha, não "Valor Total Nota"). Granularidade do faturamento = item de produto, mesma granularidade de Quantidade e Peso Líquido.

**Impostos:** bloco inteiro descartado (ICMS, PIS, COFINS, IPI, Difal, FCP, ST, Plano Pagamento) — todas essas colunas ficam fora do dashboard comercial.

**Localização:** UF, Cidade, Bairro, Filial — todos mantidos.
- Cidade será cruzada com a tabela dimensão "DIVISÕES DE ÁREA - QUALY, VB e AGENER.xlsx" para derivar a Região.

**Produto e hierarquia:** Produto, Marca, Departamento, Seção, Família, Referência, Categoria, Quantidade, Peso Líquido — todos mantidos.
- Hierarquia real: Departamento (4 valores: PET FOOD, PET VET, PET CARE, BRINDES) → Seção (= Fornecedor/Distribuidor, ex: ROYAL CANIN, VETNIL, MSD) → Família → Referência → Produto.
- "Marca" é um nível diferente de "Seção": dentro de um mesmo Fornecedor (Seção) pode haver várias Marcas distintas (ex: Seção "VB Alimentos" contém Marcas como Finotrato, Besser, Japi, Treats).
- "Categoria" está vazia em ~99% das linhas atuais (1.507 de 1.518 na amostra). Mantida no schema mesmo assim, pois pode ser preenchida no futuro — não descartar a coluna.

**Identificadores técnicos:** apenas "N° Nota" mantido (útil para deduplicar/rastrear). NCM, Observação, Código de Barras EAN, N° Carregamento, N° Pedido — todos descartados. CFOP/Descrição CFOP descartados (a Classe já cobre a regra de negócio necessária).

## LISTA FINAL DE COLUNAS DO DASHBOARD (18 de 88 originais)

1. N° Nota
2. Data Emissão
3. Código Cliente/Fornecedor
4. Cliente/Fornecedor
5. Nome Fantasia
6. RCA (vendedor)
7. Valor Total (item) — base do Faturamento
8. Quantidade
9. Peso Líquido
10. Classe (regra de negócio: Venda/Devolução/Bônus/Dev.Bônus)
11. UF
12. Cidade
13. Bairro
14. Filial
15. Produto
16. Marca
17. Departamento
18. Seção (= Fornecedor)
19. Família
20. Referência
21. Categoria (vazia hoje, mantida para uso futuro)

PENDENTE (fonte futura, fora do escopo desta planilha): Grupo Econômico do cliente.
- Fonte identificada: arquivo "Agrupamento de Clientes.xlsx" (já presente na pasta do Drive). Análise e cruzamento a serem feitos em etapa posterior, após fechar o processamento da base de vendas.

## Decisão de Arquitetura — Acesso aos dados da planilha "Mês Vigente"

Decidido: Opção A — Google Sheets "Publicar na Web" como CSV (link público não-listado).
- Motivo da escolha: simplicidade de implementação, sem necessidade de credencial/conta de serviço.
- Risco aceito conscientemente: o link, mesmo não-indexado, é acessível por qualquer pessoa que o tenha. Fernando assumiu a responsabilidade de implementar mecanismos de segurança adicionais por conta própria.
- Mitigação adicional já definida: mascarar CPF de pessoas físicas (ver item abaixo) antes que o dado passe por esse link público.

## PENDENTE — Privacidade/LGPD: Mascaramento de CPF (Pessoa Física)

No processamento (script `processar_vendas.py` e qualquer pipeline futuro), adicionar uma etapa de filtro:
- Onde "Pessoa" = "F" (pessoa física, não jurídica), substituir o valor do campo CNPJ/CPF por uma máscara (ex: "XXXXX"), tanto no histórico quanto no mês vigente.
- Objetivo: evitar exposição de dado pessoal sensível (CPF) caso o link público "Publicar na Web" seja descoberto por terceiros.
- Esse filtro deve ser aplicado ANTES de qualquer dado ser exposto publicamente (ou seja, antes da publicação do link, e antes de qualquer commit no GitHub).

## Repositório GitHub do projeto
https://github.com/fernando-antunes-qualy/Projeto-Next-Level (já criado por Fernando, repositório PÚBLICO)

## Decisão de Arquitetura — Segurança de acesso ao Dashboard publicado

Descoberta importante: GitHub Pages SEMPRE publica o site de forma pública na internet,
mesmo que o repositório de origem seja privado (privacidade de repo != privacidade do
site publicado). Privacidade real de visualização só existe no plano GitHub Enterprise
Cloud (fora do escopo/orçamento deste projeto).

Risco identificado: um login feito apenas em HTML/JavaScript (como o dashboard
estático da Agener feito anteriormente) NÃO é proteção real, por dois motivos:
1. A senha verificada em JS fica visível no código-fonte para qualquer visitante.
2. Os arquivos de dados (JSON/CSV) têm endereço próprio e são publicamente acessíveis
   diretamente, independente de existir uma tela de login na página inicial.

DECISÃO CONSCIENTE (Fernando, 26/06/2026): aceitar esse risco por agora e seguir com
login em JavaScript como "barreira simples" (impede acesso casual, não impede acesso
técnico deliberado). Dado sensível (nomes de clientes/vendedores, faturamento) ficará
tecnicamente exposto a quem souber contornar essa barreira.

PENDENTE (estudar no futuro): solução de segurança real para o dashboard publicado.
Opção já identificada e validada tecnicamente: Cloudflare Access (gratuito até ~50
usuários, exige configurar domínio próprio, intercepta requisições antes de liberar
qualquer arquivo do site — login de verdade, diferente do login em JS).

## Decisão de Arquitetura — Reatribuição de Carteira (troca de RCA responsável)

Contexto: quando um RCA sai, divide território, ou troca de marca/pasta, o
histórico de vendas correspondente deve ser reatribuído a um novo RCA —
retroativamente, não só vendas futuras. Esse evento ocorre aproximadamente
1x a cada 2 meses. Critérios de reatribuição já observados: RCA completo
(troca de carteira inteira), Cidade/Bairro (divisão de região), Marca/
Departamento (troca de pasta de produto), Cliente específico. Critérios
futuros possíveis (ainda não observados): Família, Referência, UF, etc.

Hoje não existe nenhum campo no sistema de origem que já resolva isso
automaticamente (Carteira/Código Carteira e Vendedor estão sempre vazios).

Solução adotada: tabela de regras de reatribuição GENÉRICA (não травada em
uma lista fixa de tipos). Colunas da tabela:
- Tipo de Critério: o NOME de qualquer uma das 21 colunas do nosso schema
  (RCA, Cidade, Bairro, Marca, Departamento, Código Cliente, Família, etc.)
- Valor: o valor específico que identifica a linha afetada
- RCA Original: escopo opcional (só aplica a regra se o RCA atual da linha
  for esse valor) — usado para reatribuições parciais (ex: divisão de área)
- RCA Novo: o RCA que deve substituir o original

O script de processamento aplica essas regras dinamicamente: para cada
regra, localiza a coluna pelo nome em "Tipo de Critério", filtra as linhas
que batem com "Valor" (e opcionalmente com "RCA Original"), e substitui o
RCA pelo "RCA Novo". Isso é genérico o suficiente para suportar critérios
futuros (ex: Família) sem precisar redesenhar a tabela ou o script — só
adicionar uma linha nova.

Aplicado tanto no histórico quanto no mês vigente, ANTES de qualquer
agregação, garantindo consistência sem nunca precisar reabrir/reescrever
os arquivos de histórico já processados.

## Decisão de Arquitetura — Limite de tamanho do Google Sheets (importante)

Confirmado via pesquisa: Google Sheets tem limite de importação de 100MB por
arquivo E limite de 10 milhões de células por planilha. O CSV histórico
(516MB, 88 colunas) excede os DOIS limites — não pode ser convertido em uma
única planilha Google Sheets.

Decisão: o histórico será processado como uma tarefa ÚNICA (bootstrap),
separada do pipeline diário automatizado. O arquivo será dividido em
TRIMESTRES (10 arquivos para os 2,5 anos de histórico), idealmente
reexportados direto do sistema de origem, já que abrir o arquivo de 516MB
inteiro no Excel arrisca esbarrar no limite de 1.048.576 linhas do Excel.
Cada pedaço processado gera um resultado pequeno e limpo (21 colunas +
regras de negócio + regras de reatribuição aplicadas), que fica salvo
permanentemente no repositório GitHub — sem necessidade de busca "viva"
para dados históricos, já que eles não mudam (exceto na consolidação
mensal).

## Decisão de Estrutura — Planilha "Mês Vigente" no Google Sheets

A planilha do mês vigente, migrada de Excel (.xls) para Google Sheets, deve manter
as 88 colunas ORIGINAIS do relatório exportado pelo sistema (mesma estrutura, mesma
ordem) — NÃO restringir a planilha às 21 colunas do nosso schema final.

Motivo: Fernando já tem o hábito de copiar e colar o relatório COMPLETO (88 colunas)
do sistema direto na planilha do mês vigente, sem filtrar nada manualmente antes.
Manter essa estrutura preserva esse fluxo manual exatamente como já é hoje — a
seleção das 21 colunas relevantes é feita automaticamente pelo script de
processamento (`processar_vendas.py`), não pelo usuário.

Processo de migração (uma única vez, manual): no Google Drive, botão direito no
arquivo .xls → "Abrir com" → "Google Planilhas". Isso cria um novo arquivo nativo
do Sheets na mesma pasta, sem alterar o .xls original. Renomear para algo como
"Vendas - Mês Vigente" (removendo "PARCIAL" do nome, já que esse será o nome
definitivo usado dali em diante).
