### **Modelo Matemático Refinado para Otimização de Paletização**  
**Objetivo**: Maximizar a utilização do espaço em paletes, respeitando restrições físicas e operacionais, conforme implementado no código Streamlit.  

---

#### **1. Conjuntos e Parâmetros**  
| Símbolo | Descrição |  
|---------|-----------|  
| \( I \) | Conjunto de itens a serem paletizados (\( i \in I \)) |  
| \( P \) | Conjunto de paletes disponíveis (\( p \in P \)) |  
| \( K \) | Conjunto de orientações possíveis (\( k \in \{1, \dots, 6\} \), permutações de eixos) |  

**Parâmetros dos Itens**:  
| Parâmetro | Descrição |  
|-----------|-----------|  
| \( l_i, w_i, h_i \) | Dimensões (comprimento, largura, altura) do item \( i \) (em metros) |  
| \( v_i \) | Volume do item \( i \) (\( v_i = l_i \times w_i \times h_i \)) |  
| \( m_i \) | Massa do item \( i \) (em kg) |  
| \( f_i \) | Binário: 1 se o item \( i \) é frágil, 0 caso contrário |  
| \( o_i \) | Binário: 1 se o item \( i \) pode ser rotacionado, 0 caso contrário |  
| \( \pi_i \) | Prioridade do item \( i \) (1 a 5, para ponderação na função objetivo) |  

**Parâmetros das Paletes**:  
| Parâmetro | Descrição |  
|-----------|-----------|  
| \( M_p \) | Capacidade máxima de massa da palete \( p \) (em kg) |  
| \( V_p \) | Capacidade máxima de volume da palete \( p \) (em m³) |  

---

#### **2. Variáveis de Decisão**  
| Variável | Tipo | Descrição |  
|----------|------|-----------|  
| \( x_{i,p} \) | Binária | 1 se o item \( i \) está alocado na palete \( p \), 0 caso contrário |  
| \( r_{i,k} \) | Binária | 1 se o item \( i \) está na orientação \( k \), 0 caso contrário |  
| \( s_{i,j} \) | Binária | 1 se o item \( i \) está empilhado diretamente sobre o item \( j \), 0 caso contrário |  

---

#### **3. Função Objetivo**  
Maximizar o **volume total carregado**, ponderado pela prioridade dos itens:  
$$
\max \sum_{i \in I} \sum_{p \in P} x_{i,p} \cdot v_i \cdot \pi_i
$$

**Justificativa**:  
- O código implementa a ponderação por prioridade (`prioridade` no JSON de entrada).  
- A versão anterior do modelo não considerava prioridades, apenas volume puro.  

---

#### **4. Restrições**  

**4.1. Alocação Única**  
Cada item deve estar em no máximo uma palete:  
$$
\sum_{p \in P} x_{i,p} \leq 1 \quad \forall i \in I
$$

**4.2. Capacidade das Paletes**  
- **Massa**:  
  $\sum_{i \in I} x_{i,p} \cdot m_i \leq M_p \quad \forall p \in P$  
- **Volume**:  
  $\sum_{i \in I} x_{i,p} \cdot v_i \leq V_p \quad \forall p \in P$  

**4.3. Orientação dos Itens**  
- Itens rotacionáveis (\( o_i = 1 \)) devem ter exatamente uma orientação:  
  $\sum_{k \in K} r_{i,k} = 1 \quad \forall i \in I \mid o_i = 1$  
- Itens não rotacionáveis (\( o_i = 0 \)) mantêm a orientação padrão (\( k = 1 \)):  
  $r_{i,1} = 1 \quad \forall i \in I \mid o_i = 0$  

**4.4. Empilhamento**  
- **Fragilidade**: Itens frágeis não podem ser sobrepostos:  
  $f_j = 1 \Rightarrow s_{i,j} = 0 \quad \forall i, j \in I$  
- **Peso**: Itens mais pesados não podem estar sobre mais leves:  
  $s_{i,j} = 1 \Rightarrow m_i \leq m_j \quad \forall i, j \in I$  

**4.5. Não Sobreposição**  
- Implementada indiretamente no código via restrições de empilhamento e orientação.  
- Formalmente, exigiria variáveis adicionais para coordenadas 3D (não explícitas no código).  

---

#### **5. Adições do Código ao Modelo Original**  
1. **Agrupamento por Destino**:  
   - Não modelado matematicamente no código, mas os itens têm atributo `destino` para uso futuro em roteirização.  
2. **Visualização 3D**:  
   - O código usa `$r_{i,k}$` para renderizar a orientação final dos itens.  

---

#### **6. Exemplo de Instância**  
Dados de entrada no código (exemplo):  
```python
itens = [
    {'id': 0, 'l': 0.5, 'w': 0.3, 'h': 0.4, 'mass': 20, 'f': 1, 'o': 0, 'prioridade': 3},
    {'id': 1, 'l': 0.6, 'w': 0.2, 'h': 0.3, 'mass': 15, 'f': 0, 'o': 1, 'prioridade': 5}
]
pallet_config = {'capacidade_massa': 1000, 'capacidade_volume': 2.16}
```

**Tradução para o Modelo**:  
- $I = \{0, 1\} \), \( P = \{0\}$ (1 palete).  
- Restrições:  
  - $x_{0,0} \cdot 20 + x_{1,0} \cdot 15 \leq 1000$ (massa),  
  - $x_{0,0} \cdot 0.06 + x_{1,0} \cdot 0.036 \leq 2.16$ (volume).  

---

#### **7. Melhorias em Relação ao Modelo Anterior**  
1. **Prioridades na Função Objetivo**:  
   - O modelo original maximizava apenas volume, ignorando criticidade dos itens.  
2. **Orientação Explícita**:  
   - Variáveis $r_{i,k}$ foram formalizadas para refletir o código.  
3. **Restrições de Empilhamento**:  
   - Mais claras e alinhadas com a implementação (`f_i` e `s_{i,j}`).  

---
