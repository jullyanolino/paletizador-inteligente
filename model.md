Objetivo geral

Maximizar a utilização do espaço interno de um caminhão (volume cúbico), respeitando:

Peso máximo por eixo

Regras de empilhamento

Fragilidade e orientação da carga

Agrupamento por destino (para roteirização posterior)


---

1.1. Variáveis e parâmetros

Sejam:

: conjunto de itens a serem carregados

: conjunto de paletes disponíveis

: conjunto de blocos do caminhão (posição 3D discretizada)


---

▶ Parâmetros dos itens

Para cada item :

: dimensões (comprimento, largura, altura)

: volume

: massa

: é frágil?

: pode ser girado/orientado?

: destino



---

▶ Paletes e caminhão

Paletes têm capacidade máxima  (massa) e  (volume)

Caminhão tem espaço  (dimensões)

Discretizamos o caminhão em blocos cúbicos



---

1.2. Variáveis de decisão

: item  está no palete ?

: palete  está colocado na posição ?

: item  está diretamente no bloco ? (apenas se sem palete)

: orientação do item (6 possibilidades cúbicas)



---

1.3. Função objetivo

Maximizar o volume total carregado:

$$\max \sum_{i \in I} \sum_{p \in P} x_{i,p} \cdot v_i$$

ou, se quiser usar apenas o volume cúbico útil do caminhão:

$$\max \sum_{p \in P} \sum_{b \in B} y_{p,b} \cdot V_P$$


---

1.4. Restrições principais

🟩 1. Capacidade de massa da palete:

$$\sum_{i \in I} x_{i,p} \cdot m_i \leq M_P, \quad \forall p \in P$$

🟩 2. Capacidade volumétrica da palete:

$$\sum_{i \in I} x_{i,p} \cdot v_i \leq V_P, \quad \forall p \in P$$

🟩 3. Um item em apenas uma palete ou diretamente no caminhão:

$$\sum_{p \in P} x_{i,p} + \sum_{b \in B} z_{i,b} \leq 1, \quad \forall i \in I$$

🟩 4. Restrições de empilhamento:

Não empilhar item frágil

Item mais pesado não pode ficar sobre mais leve

$\text{Se } f_i = 1 \Rightarrow \text{não pode haver nenhum item sobre } i$

$\text{Se } i \text{ está sobre } j \Rightarrow m_i \leq m_j$

🟩 5. Restrições espaciais:

Itens não podem ultrapassar o volume do caminhão

Itens/paletes não podem se sobrepor

Coordenadas tridimensionais devem ser não colidentes


Regras Adicionais

1. Empilhamento com fragilidade

Um item frágil não pode ter outro item acima dele.

Um item só pode ser empilhado sobre outro se ele for mais leve ou se o de baixo não for frágil.


---

2. Orientação dos itens

Se um item for rotacionável, ele pode ter até 6 combinações (permutações dos eixos: l, w, h).

Se não rotacionável, deve manter a orientação original.


---

🔢 Modelo Matemático (refatorado)

🔧 Novas variáveis

: orientação do item  no modo , ou uma simplificação binária com booleanos

: item  está sobre o item

: frágil?


---

🔒 Novas restrições

(R1) Respeitar fragilidade:

$$f_j = 1 \Rightarrow \sum_i a_{i,j} = 0$$

(R2) Item mais pesado só pode estar sobre item mais leve:

$$a_{i,j} = 1 \Rightarrow m_i \leq m_j$$

(R3) Orientação e rotação:

Para cada item rotacionável:

$$\sum_{k=1}^6 r_{i,k} = 1$$


---