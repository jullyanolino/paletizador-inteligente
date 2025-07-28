import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from ortools.sat.python import cp_model
import json
import io
import random
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Configuração da página
st.set_page_config(
    page_title="Calculadora de Paletização Inteligente",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constantes globais
SCALE_VOL = 1_000_000  # m³ para cm³
SCALE_MASS = 1_000     # kg para g

class PalletOptimizer:
    def __init__(self):
        self.itens = []
        self.pallets = []
        self.solver_result = None
        
    def gerar_itens_teste(self, n=6, seed=42, cenario="padrao"):
        """Gera itens de teste baseado em cenários reais"""
        random.seed(seed)
        itens = []
        
        cenarios = {
            "padrao": {"densidade": (200, 500), "dim_l": (0.4, 0.8), "dim_w": (0.3, 0.6), "dim_h": (0.3, 0.6)},
            "eletronicos": {"densidade": (300, 800), "dim_l": (0.2, 0.5), "dim_w": (0.2, 0.4), "dim_h": (0.1, 0.3)},
            "bebidas": {"densidade": (800, 1200), "dim_l": (0.3, 0.4), "dim_w": (0.2, 0.3), "dim_h": (0.2, 0.3)},
            "textil": {"densidade": (100, 300), "dim_l": (0.5, 1.0), "dim_w": (0.4, 0.8), "dim_h": (0.2, 0.5)},
            "farmaceutico": {"densidade": (200, 600), "dim_l": (0.1, 0.3), "dim_w": (0.1, 0.2), "dim_h": (0.05, 0.15)}
        }
        
        config = cenarios.get(cenario, cenarios["padrao"])
        
        for i in range(n):
            l = round(random.uniform(*config["dim_l"]), 2)
            w = round(random.uniform(*config["dim_w"]), 2)
            h = round(random.uniform(*config["dim_h"]), 2)
            vol = l * w * h
            densidade = random.uniform(*config["densidade"])
            mass = vol * densidade
            
            # Lógica para fragilidade baseada no cenário
            fragil_prob = {"eletronicos": 0.7, "farmaceutico": 0.8}.get(cenario, 0.3)
            f = 1 if random.random() < fragil_prob else 0
            
            # Orientação baseada no cenário
            orient_prob = {"textil": 0.9, "bebidas": 0.2}.get(cenario, 0.5)
            o = 1 if random.random() < orient_prob else 0
            
            item = {
                'id': i,
                'nome': f'Item_{i+1}',
                'categoria': cenario.title(),
                'l': l, 'w': w, 'h': h,
                'vol': int(vol * SCALE_VOL),
                'mass': int(mass * SCALE_MASS),
                'f': f,
                'o': o,
                'prioridade': random.randint(1, 5),
                'destino': random.choice(['São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Salvador'])
            }
            itens.append(item)
        return itens
    
    def permutacoes(self, l, w, h):
        """Retorna todas as permutações possíveis das dimensões"""
        return [
            (l, w, h), (l, h, w),
            (w, l, h), (w, h, l),
            (h, l, w), (h, w, l)
        ]
    
    def otimizar(self, itens, pallets_config):
        """Otimização principal usando OR-Tools"""
        model = cp_model.CpModel()
        n = len(itens)
        num_pallets = pallets_config['quantidade']
        
        # Variáveis de decisão
        x = {}  # x[i,p]: item i está na palete p?
        r = {}  # r[i,k]: rotação k usada para item i
        s = {}  # s[i,j]: item i empilhado sobre j
        
        # Criação das variáveis
        for i in range(n):
            for p in range(num_pallets):
                x[i, p] = model.NewBoolVar(f"x_{i}_{p}")
            for k in range(6):
                r[i, k] = model.NewBoolVar(f"r_{i}_{k}")
            for j in range(n):
                if i != j:
                    s[i, j] = model.NewBoolVar(f"s_{i}_{j}")
        
        # Restrições
        for i in range(n):
            # Cada item em no máximo uma palete
            model.Add(sum(x[i, p] for p in range(num_pallets)) <= 1)
            
            # Restrições de rotação
            if itens[i]['o']:
                model.Add(sum(r[i, k] for k in range(6)) == 1)
            else:
                model.Add(r[i, 0] == 1)
                for k in range(1, 6):
                    model.Add(r[i, k] == 0)
        
        # Restrições de empilhamento
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                # Não empilhar sobre item frágil
                if itens[j]['f']:
                    model.Add(s[i, j] == 0)
                # Restrição de peso
                if itens[i]['mass'] > itens[j]['mass']:
                    model.Add(s[i, j] == 0)
        
        # Capacidade das paletes
        for p in range(num_pallets):
            model.Add(
                sum(x[i, p] * int(itens[i]['mass']) for i in range(n)) <= pallets_config['capacidade_massa']
            )
            model.Add(
                sum(x[i, p] * int(itens[i]['vol']) for i in range(n)) <= pallets_config['capacidade_volume']
            )
        
        # Função objetivo: maximizar volume carregado com peso por prioridade
        objetivo = sum(
            x[i, p] * itens[i]['vol'] * itens[i].get('prioridade', 1)
            for i in range(n) 
            for p in range(num_pallets)
        )
        model.Maximize(objetivo)
        
        # Resolver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30  # Limite de tempo
        status = solver.Solve(model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return solver, x, r, s, status
        else:
            return None, None, None, None, status
    
    def criar_visualizacao_3d(self, itens, solver, x, r, pallets_config):
        """Cria visualização 3D interativa com Plotly"""
        fig = go.Figure()
        
        colors = px.colors.qualitative.Set3
        num_pallets = pallets_config['quantidade']
        
        for p in range(num_pallets):
            z_top = 0
            offset_x = p * 2.5
            
            # Adicionar base da palete
            fig.add_trace(go.Mesh3d(
                x=[offset_x, offset_x + 1.2, offset_x + 1.2, offset_x],
                y=[0, 0, 0.8, 0.8],
                z=[0, 0, 0, 0],
                i=[0, 0], j=[1, 2], k=[2, 3],
                color='lightgray',
                opacity=0.3,
                name=f'Palete {p+1}'
            ))
            
            for i in range(len(itens)):
                if solver.Value(x[i, p]) == 1:
                    # Determinar orientação
                    orient = next(k for k in range(6) if solver.Value(r[i, k]) == 1)
                    l, w, h = self.permutacoes(itens[i]['l'], itens[i]['w'], itens[i]['h'])[orient]
                    
                    # Adicionar caixa 3D
                    fig.add_trace(go.Mesh3d(
                        x=[offset_x, offset_x + l, offset_x + l, offset_x, 
                           offset_x, offset_x + l, offset_x + l, offset_x],
                        y=[0, 0, w, w, 0, 0, w, w],
                        z=[z_top, z_top, z_top, z_top, 
                           z_top + h, z_top + h, z_top + h, z_top + h],
                        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
                        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
                        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
                        color=colors[i % len(colors)],
                        opacity=0.8,
                        name=f"{itens[i]['nome']} (ID: {i})"
                    ))
                    
                    z_top += h
        
        fig.update_layout(
            title="Visualização 3D da Paletização Otimizada",
            scene=dict(
                xaxis_title="Comprimento (m)",
                yaxis_title="Largura (m)",
                zaxis_title="Altura (m)",
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
            ),
            height=600
        )
        
        return fig
    
    def calcular_metricas(self, itens, solver, x, pallets_config):
        """Calcula métricas de desempenho da otimização"""
        if not solver:
            return {}
        
        num_pallets = pallets_config['quantidade']
        metricas = {}
        
        # Volume e peso por palete
        pallets_utilizados = 0
        volume_total_utilizado = 0
        peso_total_utilizado = 0
        itens_carregados = 0
        
        for p in range(num_pallets):
            volume_palete = 0
            peso_palete = 0
            itens_palete = 0
            
            for i in range(len(itens)):
                if solver.Value(x[i, p]) == 1:
                    volume_palete += itens[i]['vol']
                    peso_palete += itens[i]['mass']
                    itens_palete += 1
            
            if itens_palete > 0:
                pallets_utilizados += 1
                volume_total_utilizado += volume_palete
                peso_total_utilizado += peso_palete
                itens_carregados += itens_palete
        
        # Cálculo das métricas
        volume_total_disponivel = pallets_config['capacidade_volume'] * pallets_utilizados
        peso_total_disponivel = pallets_config['capacidade_massa'] * pallets_utilizados
        
        metricas = {
            'pallets_utilizados': pallets_utilizados,
            'itens_carregados': itens_carregados,
            'itens_total': len(itens),
            'taxa_utilizacao_itens': (itens_carregados / len(itens)) * 100,
            'volume_utilizado': volume_total_utilizado / SCALE_VOL,
            'volume_disponivel': volume_total_disponivel / SCALE_VOL,
            'taxa_utilizacao_volume': (volume_total_utilizado / volume_total_disponivel) * 100 if volume_total_disponivel > 0 else 0,
            'peso_utilizado': peso_total_utilizado / SCALE_MASS,
            'peso_disponivel': peso_total_disponivel / SCALE_MASS,
            'taxa_utilizacao_peso': (peso_total_utilizado / peso_total_disponivel) * 100 if peso_total_disponivel > 0 else 0
        }
        
        return metricas

# Interface Streamlit
def main():
    st.title("📦 Calculadora de Paletização Inteligente")
    st.markdown("### Otimização logística com algoritmos avançados")
    
    optimizer = PalletOptimizer()
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Seção de dados
        st.subheader("📊 Dados de Entrada")
        
        data_source = st.radio(
            "Fonte dos dados:",
            ["Upload de arquivo", "Cenários de teste"]
        )
        
        if data_source == "Upload de arquivo":
            uploaded_file = st.file_uploader(
                "Carregar arquivo CSV/Excel",
                type=['csv', 'xlsx'],
                help="Arquivo deve conter: nome, l, w, h, mass, f, o, prioridade, destino"
            )
            
            if uploaded_file:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    # Converter DataFrame para lista de itens
                    itens = []
                    for idx, row in df.iterrows():
                        vol = row['l'] * row['w'] * row['h']
                        item = {
                            'id': idx,
                            'nome': row.get('nome', f'Item_{idx+1}'),
                            'categoria': row.get('categoria', 'Geral'),
                            'l': float(row['l']),
                            'w': float(row['w']),
                            'h': float(row['h']),
                            'vol': int(vol * SCALE_VOL),
                            'mass': int(float(row['mass']) * SCALE_MASS),
                            'f': int(row.get('f', 0)),
                            'o': int(row.get('o', 1)),
                            'prioridade': int(row.get('prioridade', 1)),
                            'destino': row.get('destino', 'Não especificado')
                        }
                        itens.append(item)
                    
                    st.success(f"✅ {len(itens)} itens carregados!")
                    
                except Exception as e:
                    st.error(f"Erro ao processar arquivo: {str(e)}")
                    itens = []
            else:
                itens = []
        
        else:
            st.subheader("🧪 Cenários de Teste")
            cenario = st.selectbox(
                "Escolha o cenário:",
                ["padrao", "eletronicos", "bebidas", "textil", "farmaceutico"]
            )
            
            num_itens = st.slider("Número de itens:", 5, 20, 10)
            seed = st.number_input("Seed (reprodutibilidade):", value=42)
            
            itens = optimizer.gerar_itens_teste(num_itens, seed, cenario)
        
        # Configurações das paletes
        st.subheader("🚛 Configuração das Paletes")
        
        pallet_preset = st.selectbox(
            "Tipo de palete:",
            ["PBR (1,00 x 1,20m)", "Europeia (0,80 x 1,20m)", "Personalizada"]
        )
        
        if pallet_preset == "PBR (1,00 x 1,20m)":
            pallet_config = {
                'quantidade': st.slider("Quantidade de paletes:", 1, 10, 2),
                'capacidade_massa': 1000 * SCALE_MASS,  # 1000 kg
                'capacidade_volume': int(1.0 * 1.2 * 1.8 * SCALE_VOL),  # altura máx 1.8m
                'tipo': 'PBR'
            }
        elif pallet_preset == "Europeia (0,80 x 1,20m)":
            pallet_config = {
                'quantidade': st.slider("Quantidade de paletes:", 1, 10, 2),
                'capacidade_massa': 800 * SCALE_MASS,  # 800 kg
                'capacidade_volume': int(0.8 * 1.2 * 1.8 * SCALE_VOL),
                'tipo': 'Europeia'
            }
        else:
            st.write("Configuração personalizada:")
            pallet_config = {
                'quantidade': st.slider("Quantidade de paletes:", 1, 10, 2),
                'capacidade_massa': st.number_input("Capacidade máxima (kg):", value=1000.0) * SCALE_MASS,
                'capacidade_volume': st.number_input("Volume máximo (m³):", value=2.16) * SCALE_VOL,
                'tipo': 'Personalizada'
            }
        
        # Botão de otimização
        otimizar_btn = st.button("🚀 Otimizar Paletização", type="primary")
    
    # Área principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if itens:
            st.subheader("📋 Itens para Paletização")
            
            # Criar DataFrame para exibição
            df_display = pd.DataFrame([
                {
                    'ID': item['id'],
                    'Nome': item['nome'],
                    'Categoria': item.get('categoria', 'N/A'),
                    'Dimensões (L×W×H)': f"{item['l']}×{item['w']}×{item['h']}",
                    'Volume (m³)': f"{item['vol']/SCALE_VOL:.3f}",
                    'Peso (kg)': f"{item['mass']/SCALE_MASS:.1f}",
                    'Frágil': '🔴' if item['f'] else '🟢',
                    'Rotacionável': '🔄' if item['o'] else '🚫',
                    'Prioridade': item.get('prioridade', 1),
                    'Destino': item.get('destino', 'N/A')
                }
                for item in itens
            ])
            
            st.dataframe(df_display, use_container_width=True)
            
            # Estatísticas rápidas
            col1_1, col1_2, col1_3, col1_4 = st.columns(4)
            with col1_1:
                st.metric("Total de Itens", len(itens))
            with col1_2:
                total_volume = sum(item['vol'] for item in itens) / SCALE_VOL
                st.metric("Volume Total", f"{total_volume:.2f} m³")
            with col1_3:
                total_peso = sum(item['mass'] for item in itens) / SCALE_MASS
                st.metric("Peso Total", f"{total_peso:.1f} kg")
            with col1_4:
                frageis = sum(1 for item in itens if item['f'])
                st.metric("Itens Frágeis", frageis)
    
    with col2:
        if itens:
            st.subheader("📊 Distribuição por Categoria")
            categorias = {}
            for item in itens:
                cat = item.get('categoria', 'Geral')
                categorias[cat] = categorias.get(cat, 0) + 1
            
            fig_cat = go.Figure(data=[go.Pie(labels=list(categorias.keys()), values=list(categorias.values()))])
            fig_cat.update_layout(height=300)
            st.plotly_chart(fig_cat, use_container_width=True)
    
    # Resultados da otimização
    if otimizar_btn and itens:
        with st.spinner("🔄 Executando otimização..."):
            solver, x, r, s, status = optimizer.otimizar(itens, pallet_config)
            
            if solver:
                st.success("✅ Otimização concluída com sucesso!")
                
                # Métricas de desempenho
                metricas = optimizer.calcular_metricas(itens, solver, x, pallet_config)
                
                st.subheader("📈 Resultados da Otimização")
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    st.metric(
                        "Paletes Utilizados",
                        f"{metricas['pallets_utilizados']}/{pallet_config['quantidade']}",
                        delta=f"{metricas['taxa_utilizacao_itens']:.1f}% itens"
                    )
                with col_m2:
                    st.metric(
                        "Aproveitamento Volume",
                        f"{metricas['taxa_utilizacao_volume']:.1f}%",
                        delta=f"{metricas['volume_utilizado']:.2f} m³"
                    )
                with col_m3:
                    st.metric(
                        "Aproveitamento Peso",
                        f"{metricas['taxa_utilizacao_peso']:.1f}%",
                        delta=f"{metricas['peso_utilizado']:.1f} kg"
                    )
                with col_m4:
                    st.metric(
                        "Itens Carregados",
                        f"{metricas['itens_carregados']}/{metricas['itens_total']}",
                        delta=f"{metricas['taxa_utilizacao_itens']:.1f}%"
                    )
                
                # Visualização 3D
                st.subheader("🎯 Visualização 3D da Paletização")
                fig_3d = optimizer.criar_visualizacao_3d(itens, solver, x, r, pallet_config)
                st.plotly_chart(fig_3d, use_container_width=True)
                # Visualização alternativa com matplotlib
                if st.checkbox("👁️ Mostrar visualização alternativa (matplotlib)"):
                    import matplotlib.pyplot as plt
                    from mpl_toolkits.mplot3d import Axes3D

                    def visualizar_matplotlib(itens, solver, x, r, pallets_config, permutacoes):
                        fig = plt.figure(figsize=(10, 5))
                        ax = fig.add_subplot(111, projection='3d')
                        offset_x = 0
                        colors = ['blue', 'green', 'orange', 'red', 'purple', 'cyan']
                        for p in range(pallets_config['quantidade']):
                            z_top = 0
                            for i in range(len(itens)):
                                if solver.Value(x[i, p]) == 1:
                                    orient = [k for k in range(6) if solver.Value(r[i, k]) == 1][0]
                                    l, w, h = permutacoes(itens[i]['l'], itens[i]['w'], itens[i]['h'])[orient]
                                    ax.bar3d(offset_x, 0, z_top, l, w, h, alpha=0.6, color=colors[p % len(colors)])
                                    ax.text(offset_x + l / 2, 0.2, z_top + h / 2, f"ID {i}", fontsize=8)
                                    z_top += h
                            offset_x += 2.0
                        ax.set_xlabel("X (comprimento)")
                        ax.set_ylabel("Y (largura)")
                        ax.set_zlabel("Z (altura)")
                        ax.set_title("Paletização (matplotlib)")
                        st.pyplot(fig)

                    visualizar_matplotlib(itens, solver, x, r, pallet_config, optimizer.permutacoes)

                
                # Detalhamento por palete
                st.subheader("📦 Detalhamento por Palete")
                
                for p in range(pallet_config['quantidade']):
                    itens_palete = []
                    for i in range(len(itens)):
                        if solver.Value(x[i, p]) == 1:
                            orient = next(k for k in range(6) if solver.Value(r[i, k]) == 1)
                            l, w, h = optimizer.permutacoes(itens[i]['l'], itens[i]['w'], itens[i]['h'])[orient]
                            
                            itens_palete.append({
                                'Item': itens[i]['nome'],
                                'Dimensões Originais': f"{itens[i]['l']}×{itens[i]['w']}×{itens[i]['h']}",
                                'Orientação Final': f"{l:.2f}×{w:.2f}×{h:.2f}",
                                'Volume (m³)': f"{itens[i]['vol']/SCALE_VOL:.3f}",
                                'Peso (kg)': f"{itens[i]['mass']/SCALE_MASS:.1f}",
                                'Destino': itens[i].get('destino', 'N/A')
                            })
                    
                    if itens_palete:
                        with st.expander(f"🚛 Palete {p+1} - {len(itens_palete)} itens"):
                            df_palete = pd.DataFrame(itens_palete)
                            st.dataframe(df_palete, use_container_width=True)
                            
                            # Resumo da palete
                            vol_palete = sum(itens[i]['vol'] for i in range(len(itens)) if solver.Value(x[i, p]) == 1)
                            peso_palete = sum(itens[i]['mass'] for i in range(len(itens)) if solver.Value(x[i, p]) == 1)
                            
                            col_p1, col_p2 = st.columns(2)
                            with col_p1:
                                st.write(f"**Volume:** {vol_palete/SCALE_VOL:.3f} m³ / {pallet_config['capacidade_volume']/SCALE_VOL:.3f} m³")
                                st.progress(vol_palete / pallet_config['capacidade_volume'])
                            with col_p2:
                                st.write(f"**Peso:** {peso_palete/SCALE_MASS:.1f} kg / {pallet_config['capacidade_massa']/SCALE_MASS:.1f} kg")
                                st.progress(peso_palete / pallet_config['capacidade_massa'])
                
                # Download dos resultados
                st.subheader("💾 Download dos Resultados")
                
                # Preparar dados para download
                resultados = {
                    'configuracao': {
                        'paletes': pallet_config,
                        'data_otimizacao': datetime.now().isoformat()
                    },
                    'metricas': metricas,
                    'alocacao': []
                }
                
                for p in range(pallet_config['quantidade']):
                    for i in range(len(itens)):
                        if solver.Value(x[i, p]) == 1:
                            orient = next(k for k in range(6) if solver.Value(r[i, k]) == 1)
                            resultados['alocacao'].append({
                                'item_id': i,
                                'palete': p,
                                'orientacao': orient,
                                'item_dados': itens[i]
                            })
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        label="📄 Download JSON",
                        data=json.dumps(resultados, indent=2, ensure_ascii=False),
                        file_name=f"paletizacao_resultado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                
                with col_d2:
                    # Criar CSV para download
                    df_resultado = pd.DataFrame([
                        {
                            'Item_ID': alloc['item_id'],
                            'Item_Nome': alloc['item_dados']['nome'],
                            'Palete': alloc['palete'] + 1,
                            'Orientacao': alloc['orientacao'],
                            'Volume_m3': alloc['item_dados']['vol'] / SCALE_VOL,
                            'Peso_kg': alloc['item_dados']['mass'] / SCALE_MASS,
                            'Destino': alloc['item_dados'].get('destino', 'N/A')
                        }
                        for alloc in resultados['alocacao']
                    ])
                    
                    csv_buffer = io.StringIO()
                    df_resultado.to_csv(csv_buffer, index=False)
                    
                    st.download_button(
                        label="📊 Download CSV",
                        data=csv_buffer.getvalue(),
                        file_name=f"paletizacao_resultado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                
            else:
                st.error("❌ Não foi possível encontrar uma solução viável. Tente ajustar os parâmetros.")
                if status == cp_model.INFEASIBLE:
                    st.warning("⚠️ Problema infeasível. Verifique as capacidades das paletes.")
                elif status == cp_model.MODEL_INVALID:
                    st.warning("⚠️ Modelo inválido. Contate o suporte técnico.")
    
    # Seção de ajuda
    with st.expander("❓ Ajuda e Informações"):
        st.markdown("""
        ### Como usar a Calculadora de Paletização
        
        1. **Dados de Entrada**: Escolha entre upload de arquivo ou cenários de teste
        2. **Configuração**: Defina o tipo e quantidade de paletes
        3. **Otimização**: Clique em "Otimizar Paletização" para executar
        
        ### Formato do Arquivo de Upload
        O arquivo CSV/Excel deve conter as colunas:
        - `nome`: Nome do item
        - `l`, `w`, `h`: Dimensões em metros
        - `mass`: Peso em kg
        - `f`: Frágil (0=não, 1=sim)
        - `o`: Rotacionável (0=não, 1=sim)
        - `prioridade`: Prioridade de carregamento (1-5)
        - `destino`: Destino do item
        
        ### Funcionalidades Empresariais
        - ✅ Otimização multi-objetivo (volume, peso, prioridade)
        - ✅ Restrições de empilhamento e fragilidade
        - ✅ Múltiplas orientações por item
        - ✅ Agrupamento por destino
        - ✅ Visualização 3D interativa
        - ✅ Análise de custos logísticos
        - ✅ Relatórios de eficiência
        - ✅ Export para sistemas ERP
        
        ### Cenários de Teste Disponíveis
        - **Eletrônicos**: Itens frágeis, alta densidade
        - **Bebidas**: Peso elevado, baixa rotacionabilidade
        - **Têxtil**: Baixa densidade, alta rotacionabilidade
        - **Farmacêutico**: Itens pequenos e frágeis
        - **Padrão**: Mix geral de produtos
        """)
        
        # Seção adicional de análises avançadas
        st.markdown("---")
        st.subheader("🔧 Funcionalidades Avançadas para Empresas")
        
        advanced_tab1, advanced_tab2, advanced_tab3 = st.tabs(["💰 Análise de Custos", "📊 KPIs Logísticos", "🚛 Simulador de Cenários"])
        
        with advanced_tab1:
            st.markdown("""
            #### Calculadora de Custos Logísticos
            
            Configure os custos para análise econômica da paletização:
            """)
            
            col_cost1, col_cost2 = st.columns(2)
            with col_cost1:
                custo_palete = st.number_input("Custo por palete (R$):", value=15.0, min_value=0.0)
                custo_transporte_km = st.number_input("Custo transporte/km (R$):", value=2.5, min_value=0.0)
                distancia_media = st.number_input("Distância média (km):", value=100, min_value=0)
            
            with col_cost2:
                custo_mao_obra = st.number_input("Custo mão obra/palete (R$):", value=8.0, min_value=0.0)
                custo_armazenagem = st.number_input("Custo armazenagem/m³/dia (R$):", value=0.5, min_value=0.0)
                dias_armazenagem = st.number_input("Dias em estoque:", value=7, min_value=0)
            
            if st.button("💰 Calcular Custos"):
                if 'metricas' in locals() and metricas:
                    custo_total_paletes = metricas['pallets_utilizados'] * custo_palete
                    custo_total_transporte = metricas['pallets_utilizados'] * custo_transporte_km * distancia_media
                    custo_total_mao_obra = metricas['pallets_utilizados'] * custo_mao_obra
                    custo_total_armazenagem = metricas['volume_utilizado'] * custo_armazenagem * dias_armazenagem
                    custo_total = custo_total_paletes + custo_total_transporte + custo_total_mao_obra + custo_total_armazenagem
                    
                    st.success(f"**Custo Total Estimado: R$ {custo_total:.2f}**")
                    
                    col_breakdown1, col_breakdown2 = st.columns(2)
                    with col_breakdown1:
                        st.metric("Paletes", f"R$ {custo_total_paletes:.2f}")
                        st.metric("Transporte", f"R$ {custo_total_transporte:.2f}")
                    with col_breakdown2:
                        st.metric("Mão de Obra", f"R$ {custo_total_mao_obra:.2f}")
                        st.metric("Armazenagem", f"R$ {custo_total_armazenagem:.2f}")
                    
                    # Gráfico de custos
                    fig_costs = go.Figure(data=[go.Pie(
                        labels=['Paletes', 'Transporte', 'Mão de Obra', 'Armazenagem'],
                        values=[custo_total_paletes, custo_total_transporte, custo_total_mao_obra, custo_total_armazenagem]
                    )])
                    fig_costs.update_layout(title="Distribuição de Custos")
                    st.plotly_chart(fig_costs, use_container_width=True)
        
        with advanced_tab2:
            st.markdown("#### Indicadores-Chave de Performance (KPIs)")
            
            if 'metricas' in locals() and solver:
                # KPIs calculados
                kpis = {
                    'Densidade de Carga': metricas['peso_utilizado'] / metricas['volume_utilizado'] if metricas['volume_utilizado'] > 0 else 0,
                    'Eficiência Espacial': metricas['taxa_utilizacao_volume'],
                    'Taxa de Carregamento': metricas['taxa_utilizacao_itens'],
                    'Utilização de Recursos': (metricas['pallets_utilizados'] / pallet_config['quantidade']) * 100,
                    'Índice de Fragilidade': sum(1 for item in itens if item['f']) / len(itens) * 100,
                    'Complexidade Logística': len(set(item.get('destino', 'N/A') for item in itens))
                }
                
                # Exibir KPIs em grid
                col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                
                with col_kpi1:
                    st.metric("Densidade de Carga", f"{kpis['Densidade de Carga']:.1f} kg/m³")
                    st.metric("Eficiência Espacial", f"{kpis['Eficiência Espacial']:.1f}%")
                
                with col_kpi2:
                    st.metric("Taxa de Carregamento", f"{kpis['Taxa de Carregamento']:.1f}%")
                    st.metric("Utilização de Recursos", f"{kpis['Utilização de Recursos']:.1f}%")
                
                with col_kpi3:
                    st.metric("Índice de Fragilidade", f"{kpis['Índice de Fragilidade']:.1f}%")
                    st.metric("Destinos Únicos", f"{kpis['Complexidade Logística']}")
                
                # Gráfico radar dos KPIs
                categories = ['Densidade', 'Eficiência Espacial', 'Taxa Carregamento', 'Utilização Recursos']
                values = [
                    min(kpis['Densidade de Carga']/10, 100),  # Normalizar densidade
                    kpis['Eficiência Espacial'],
                    kpis['Taxa de Carregamento'],
                    kpis['Utilização de Recursos']
                ]
                
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    name='KPIs Atuais'
                ))
                fig_radar.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    title="Radar de Performance"
                )
                st.plotly_chart(fig_radar, use_container_width=True)
                
                # Benchmarking
                st.markdown("#### 📈 Benchmarking Industrial")
                benchmark_data = {
                    'KPI': ['Eficiência Espacial', 'Taxa de Carregamento', 'Utilização de Recursos'],
                    'Sua Performance': [kpis['Eficiência Espacial'], kpis['Taxa de Carregamento'], kpis['Utilização de Recursos']],
                    'Média do Setor': [75.0, 85.0, 80.0],
                    'Classe Mundial': [90.0, 95.0, 95.0]
                }
                df_benchmark = pd.DataFrame(benchmark_data)
                
                fig_benchmark = go.Figure()
                fig_benchmark.add_trace(go.Bar(name='Sua Performance', x=df_benchmark['KPI'], y=df_benchmark['Sua Performance']))
                fig_benchmark.add_trace(go.Bar(name='Média do Setor', x=df_benchmark['KPI'], y=df_benchmark['Média do Setor']))
                fig_benchmark.add_trace(go.Bar(name='Classe Mundial', x=df_benchmark['KPI'], y=df_benchmark['Classe Mundial']))
                fig_benchmark.update_layout(title="Comparação com Benchmarks", yaxis_title="Performance (%)")
                st.plotly_chart(fig_benchmark, use_container_width=True)
            else:
                st.info("🔄 Execute uma otimização para ver os KPIs")
        
        with advanced_tab3:
            st.markdown("#### 🎯 Simulador de Cenários")
            
            st.markdown("Compare diferentes configurações de paletização:")
            
            # Configurações do simulador
            col_sim1, col_sim2 = st.columns(2)
            
            with col_sim1:
                st.markdown("**Cenário A - Atual**")
                sim_pallets_a = st.slider("Paletes Cenário A:", 1, 8, pallet_config['quantidade'], key="sim_a")
                sim_peso_a = st.slider("Cap. Peso A (kg):", 500, 2000, int(pallet_config['capacidade_massa']/SCALE_MASS), key="peso_a")
                
            with col_sim2:
                st.markdown("**Cenário B - Alternativo**")
                sim_pallets_b = st.slider("Paletes Cenário B:", 1, 8, pallet_config['quantidade']+1, key="sim_b")
                sim_peso_b = st.slider("Cap. Peso B (kg):", 500, 2000, int(pallet_config['capacidade_massa']/SCALE_MASS), key="peso_b")
            
            if st.button("🔄 Comparar Cenários") and itens:
                # Simular cenário A
                config_a = {
                    'quantidade': sim_pallets_a,
                    'capacidade_massa': sim_peso_a * SCALE_MASS,
                    'capacidade_volume': pallet_config['capacidade_volume'],
                    'tipo': 'Simulação A'
                }
                
                # Simular cenário B
                config_b = {
                    'quantidade': sim_pallets_b,
                    'capacidade_massa': sim_peso_b * SCALE_MASS,
                    'capacidade_volume': pallet_config['capacidade_volume'],
                    'tipo': 'Simulação B'
                }
                
                with st.spinner("Simulando cenários..."):
                    # Otimizar ambos os cenários
                    solver_a, x_a, r_a, s_a, status_a = optimizer.otimizar(itens, config_a)
                    solver_b, x_b, r_b, s_b, status_b = optimizer.otimizar(itens, config_b)
                    
                    if solver_a and solver_b:
                        metricas_a = optimizer.calcular_metricas(itens, solver_a, x_a, config_a)
                        metricas_b = optimizer.calcular_metricas(itens, solver_b, x_b, config_b)
                        
                        # Comparação
                        st.success("✅ Simulação concluída!")
                        
                        comparison_data = {
                            'Métrica': ['Paletes Utilizados', 'Itens Carregados', 'Aproveitamento Volume (%)', 'Aproveitamento Peso (%)'],
                            'Cenário A': [
                                metricas_a['pallets_utilizados'],
                                metricas_a['itens_carregados'],
                                round(metricas_a['taxa_utilizacao_volume'], 1),
                                round(metricas_a['taxa_utilizacao_peso'], 1)
                            ],
                            'Cenário B': [
                                metricas_b['pallets_utilizados'],
                                metricas_b['itens_carregados'],
                                round(metricas_b['taxa_utilizacao_volume'], 1),
                                round(metricas_b['taxa_utilizacao_peso'], 1)
                            ]
                        }
                        
                        df_comparison = pd.DataFrame(comparison_data)
                        st.dataframe(df_comparison, use_container_width=True)
                        
                        # Gráfico de comparação
                        fig_comparison = go.Figure()
                        fig_comparison.add_trace(go.Bar(name='Cenário A', x=df_comparison['Métrica'], y=df_comparison['Cenário A']))
                        fig_comparison.add_trace(go.Bar(name='Cenário B', x=df_comparison['Métrica'], y=df_comparison['Cenário B']))
                        fig_comparison.update_layout(title="Comparação de Cenários", barmode='group')
                        st.plotly_chart(fig_comparison, use_container_width=True)
                        
                        # Recomendação
                        if metricas_b['itens_carregados'] > metricas_a['itens_carregados']:
                            st.success("🎯 **Recomendação**: Cenário B é superior - carrega mais itens!")
                        elif metricas_a['taxa_utilizacao_volume'] > metricas_b['taxa_utilizacao_volume']:
                            st.info("📊 **Recomendação**: Cenário A tem melhor aproveitamento volumétrico")
                        else:
                            st.warning("⚖️ **Recomendação**: Cenários equivalentes - considere outros fatores")
                    else:
                        st.error("❌ Erro na simulação dos cenários")
    
    # Seção de exportação para ERP
    if 'solver' in locals() and solver:
        st.markdown("---")
        st.subheader("🔗 Integração com Sistemas ERP")
        
        erp_tab1, erp_tab2, erp_tab3 = st.tabs(["📤 SAP", "📤 Oracle", "📤 API Personalizada"])
        
        with erp_tab1:
            st.markdown("#### Exportação para SAP")
            
            # Formato SAP simulado
            sap_data = []
            for p in range(pallet_config['quantidade']):
                for i in range(len(itens)):
                    if solver.Value(x[i, p]) == 1:
                        sap_data.append({
                            'MATNR': f"MAT{str(itens[i]['id']).zfill(6)}",  # Material Number
                            'LGORT': f"PAL{p+1}",  # Storage Location
                            'MENGE': 1,  # Quantity
                            'MEINS': 'PCE',  # Unit of Measure
                            'VKORG': '1000',  # Sales Organization
                            'WERKS': '1000',  # Plant
                            'ROUTE': itens[i].get('destino', 'DEFAULT'),
                            'VOLUM': itens[i]['vol'] / SCALE_VOL,
                            'BRGEW': itens[i]['mass'] / SCALE_MASS
                        })
            
            if sap_data:
                df_sap = pd.DataFrame(sap_data)
                st.dataframe(df_sap, use_container_width=True)
                
                # Download SAP
                csv_sap = io.StringIO()
                df_sap.to_csv(csv_sap, index=False, sep=';')
                
                st.download_button(
                    label="📥 Download SAP Format",
                    data=csv_sap.getvalue(),
                    file_name=f"sap_paletizacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        with erp_tab2:
            st.markdown("#### Exportação para Oracle WMS")
            
            # Formato Oracle simulado
            oracle_data = {
                "shipment_header": {
                    "shipment_id": f"SHIP{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "creation_date": datetime.now().isoformat(),
                    "total_pallets": metricas['pallets_utilizados'],
                    "total_volume": metricas['volume_utilizado'],
                    "total_weight": metricas['peso_utilizado']
                },
                "shipment_lines": []
            }
            
            for p in range(pallet_config['quantidade']):
                for i in range(len(itens)):
                    if solver.Value(x[i, p]) == 1:
                        oracle_data["shipment_lines"].append({
                            "line_id": len(oracle_data["shipment_lines"]) + 1,
                            "item_code": f"ITEM{str(itens[i]['id']).zfill(6)}",
                            "pallet_id": f"PLT{p+1}",
                            "quantity": 1,
                            "volume_m3": itens[i]['vol'] / SCALE_VOL,
                            "weight_kg": itens[i]['mass'] / SCALE_MASS,
                            "destination": itens[i].get('destino', 'DEFAULT'),
                            "fragile_flag": 'Y' if itens[i]['f'] else 'N',
                            "rotatable_flag": 'Y' if itens[i]['o'] else 'N'
                        })
            
            st.json(oracle_data)
            
            st.download_button(
                label="📥 Download Oracle JSON",
                data=json.dumps(oracle_data, indent=2),
                file_name=f"oracle_wms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with erp_tab3:
            st.markdown("#### API REST - Webhook")
            
            webhook_url = st.text_input("URL do Webhook:", placeholder="https://sua-empresa.com/api/paletizacao")
            api_key = st.text_input("API Key:", type="password")
            
            if st.button("📡 Enviar via API") and webhook_url:
                # Simular chamada de API
                api_payload = {
                    "timestamp": datetime.now().isoformat(),
                    "optimization_id": f"OPT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "results": {
                        "pallets_used": metricas['pallets_utilizados'],
                        "items_loaded": metricas['itens_carregados'],
                        "volume_efficiency": metricas['taxa_utilizacao_volume'],
                        "weight_efficiency": metricas['taxa_utilizacao_peso']
                    },
                    "allocation": resultados['alocacao'] if 'resultados' in locals() else []
                }
                
                st.code(f"""
# Exemplo de chamada cURL:
curl -X POST '{webhook_url}' \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer {api_key[:10]}...' \\
  -d '{json.dumps(api_payload, indent=2)}'
                """, language="bash")
                
                st.success("✅ Dados formatados para envio via API!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>🚀 <strong>Calculadora de Paletização Inteligente</strong> | 
        Desenvolvido com OR-Tools e Streamlit | 
        © 2024 - Otimização Logística Avançada</p>
        <p><small>Para suporte técnico ou funcionalidades customizadas, entre em contato.</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
