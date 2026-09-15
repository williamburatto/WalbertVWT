# -*- coding: utf-8 -*-
import pandas as pd
from data_sc import CROP_PARAMS, get_sc_dataframe, calculate_potentials

class BiomassProducerAgent:
    """Agent representing agricultural cooperatives or farmers generating biomass residues."""
    def __init__(self, name, municipality, region, lat, lon, crop_data):
        self.name = name
        self.municipality = municipality
        self.region = region
        self.lat = lat
        self.lon = lon
        self.crop_data = crop_data # Dicionário de produção de grãos
        self.residues_total_t = 0
        self.residues_available_t = 0
        self.price_per_ton = 150.0 # R$/t (Preço básico de venda da biomassa)
        self.sold_biomass_t = 0
        self.revenue = 0.0

    def calculate_residues(self, collect_rate):
        """Calcula a quantidade de resíduo total e coletado para comercialização."""
        self.residues_total_t = 0
        for crop, amount in self.crop_data.items():
            if crop in CROP_PARAMS:
                self.residues_total_t += amount * CROP_PARAMS[crop]["residue_factor"]
        self.residues_available_t = self.residues_total_t * collect_rate
        self.sold_biomass_t = 0
        self.revenue = 0.0

    def sell_biomass(self, quantity_t, buyer_price):
        """Vende uma fração ou o total da biomassa disponível para um comprador (usina)."""
        actual_sell = min(quantity_t, self.residues_available_t - self.sold_biomass_t)
        if actual_sell > 0:
            self.sold_biomass_t += actual_sell
            self.revenue += actual_sell * buyer_price
            return actual_sell
        return 0.0


class PyrolysisPlantAgent:
    """Agent representing a local pyrolysis distributed energy utility."""
    def __init__(self, name, municipality, lat, lon, capacity_t_year):
        self.name = name
        self.municipality = municipality
        self.lat = lat
        self.lon = lon
        self.capacity_t_year = capacity_t_year # Capacidade máxima de processamento de resíduo/ano
        
        # Parâmetros econômicos básicos
        self.base_capex = (capacity_t_year / 10000.0) * 2500000.0 
        self.capex = self.base_capex
        self.opex_fixed = (self.capex * 0.05) # 5% do CAPEX em manutenção/OPEX fixo
        self.opex_variable = 0.0 # Custo de compra da biomassa + logística
        
        # Estado operacional
        self.processed_biomass_t = 0.0
        self.electricity_generated_mwh = 0.0
        self.biochar_generated_t = 0.0
        self.co2_captured_t = 0.0
        
        # Preços de venda de produtos da usina
        self.electricity_price = 550.0  # R$/MWh
        self.carbon_credit_price = 100.0 # R$/tCO2eq
        
        # Receitas e Custos
        self.revenue_electricity = 0.0
        self.revenue_carbon = 0.0
        self.total_revenue = 0.0
        self.net_profit = 0.0
        self.payback_years = float('inf')

    def apply_sbce_subsidy(self, subsidy_pct):
        """Aplica subsídio no CAPEX decorrente do fundo do leilão por consignação do SBCE."""
        self.capex = self.base_capex * (1.0 - subsidy_pct)
        self.opex_fixed = (self.capex * 0.05)

    def run_production(self, purchased_biomass, crop_mix_proportions):
        """Processa a biomassa em energia elétrica (MWh) e Biocarvão/Captura de Carbono."""
        self.processed_biomass_t = min(purchased_biomass, self.capacity_t_year)
        
        self.electricity_generated_mwh = 0.0
        self.biochar_generated_t = 0.0
        self.co2_captured_t = 0.0
        
        for crop, prop in crop_mix_proportions.items():
            if prop <= 0: continue
            crop_biomass = self.processed_biomass_t * prop
            params = CROP_PARAMS[crop]
            
            # 1. Energia Elétrica
            m_elec = 1000.0 * params["lhv"] * (1.0 / 3600.0) * params["eta"]
            self.electricity_generated_mwh += crop_biomass * m_elec
            
            # 2. Biocarvão
            biochar = crop_biomass * params["biochar_yield"]
            self.biochar_generated_t += biochar
            
            # 3. CO2 sequestrado no solo (Sequestro Estável)
            self.co2_captured_t += biochar * params["carbon_content"] * (44.0 / 12.0)
            
        # Adiciona a descarbonização extra da substituição de energia do grid fóssil
        self.co2_captured_t += self.electricity_generated_mwh * 0.1

    def calculate_finances(self, biomass_purchase_cost):
        """Calcula receitas, lucro líquido anual e tempo de retorno do investimento (Payback)."""
        self.opex_variable = biomass_purchase_cost
        self.revenue_electricity = self.electricity_generated_mwh * self.electricity_price
        self.revenue_carbon = self.co2_captured_t * self.carbon_credit_price
        self.total_revenue = self.revenue_electricity + self.revenue_carbon
        
        total_opex = self.opex_fixed + self.opex_variable
        self.net_profit = self.total_revenue - total_opex
        
        if self.net_profit > 0:
            self.payback_years = self.capex / self.net_profit
        else:
            self.payback_years = float('inf')


class IndustryAgent:
    """Agent representing an industrial consumer looking to buy green energy and meet SBCE targets."""
    def __init__(self, name, municipality, lat, lon, energy_demand_mwh, co2_emissions_target_t):
        self.name = name
        self.municipality = municipality
        self.lat = lat
        self.lon = lon
        self.energy_demand_mwh = energy_demand_mwh
        self.co2_emissions_target_t = co2_emissions_target_t # Meta legal de redução de CO2 sob o SBCE (tCO2/ano)
        
        # Custos originais de energia (energia convencional a R$ 680/MWh)
        self.original_energy_cost = energy_demand_mwh * 680.0
        
        # Resultados do mercado multiagente
        self.contracted_electricity_mwh = 0.0
        self.purchased_carbon_credits_t = 0.0
        self.new_energy_cost = 0.0
        self.carbon_credits_cost = 0.0
        self.total_decarbonization_achieved_t = 0.0
        self.decarbonization_pct = 0.0
        self.financial_savings = 0.0
        
        # Variáveis exclusivas do SBCE
        self.free_quotas_allocated = 0.0
        self.quotas_bought_in_auction = 0.0
        self.auction_cost = 0.0
        self.refund_received = 0.0
        self.penalty_paid = 0.0
        self.total_compliance_cost = 0.0

    def calculate_sbce_compliance(self, sbce_mode, auction_price, return_coeff, penalty_price=300.0):
        """Calcula os custos de conformidade da indústria com as regras do SBCE."""
        # Se as emissões não abatidas superarem o alvo legal, há necessidade de adquirir quotas no leilão ou pagar multa
        unabated_co2 = max(0.0, self.co2_emissions_target_t - self.total_decarbonization_achieved_t)
        
        if sbce_mode == "Alocação Gratuita":
            # Alta parcela de quotas gratuitas (ex: 90% das emissões obrigatórias cobertas)
            self.free_quotas_allocated = self.co2_emissions_target_t * 0.90
            uncovered_co2 = max(0.0, unabated_co2 - self.free_quotas_allocated)
            # Sem leilões obrigatórios, o resto é pago como multa direta leve ou comprado como offset
            self.quotas_bought_in_auction = 0.0
            self.auction_cost = 0.0
            self.refund_received = 0.0
            self.penalty_paid = uncovered_co2 * penalty_price * 0.5 # Multa reduzida na fase gratuita

        elif sbce_mode == "Leilão por Consignação":
            # 50% gratuito, 50% precisa ser comprado em leilão
            self.free_quotas_allocated = self.co2_emissions_target_t * 0.50
            uncovered_co2 = max(0.0, unabated_co2 - self.free_quotas_allocated)
            self.quotas_bought_in_auction = uncovered_co2
            
            # Custo bruto do leilão
            self.auction_cost = self.quotas_bought_in_auction * auction_price
            # Retorno de parte da receita para fomento sustentável (conforme o artigo de Guo et al.)
            self.refund_received = self.auction_cost * return_coeff
            self.penalty_paid = 0.0

        elif sbce_mode == "Leilão Tradicional":
            # 100% precisa ser adquirido em leilão regulado (fase de neutralidade madura)
            self.free_quotas_allocated = 0.0
            self.quotas_bought_in_auction = unabated_co2
            self.auction_cost = self.quotas_bought_in_auction * auction_price
            self.refund_received = 0.0 # Sem reembolso para a indústria
            
            # Se ultrapassar o limite sem comprar créditos, paga multa pesada
            self.penalty_paid = 0.0 

        # Custo total de conformidade sob o SBCE
        self.total_compliance_cost = self.auction_cost - self.refund_received + self.penalty_paid
        
        # Ajusta a economia financeira líquida considerando o novo custo de conformidade do SBCE
        original_compliance_cost = self.co2_emissions_target_t * 0.10 * penalty_price # Linha de base sem SBCE ativo
        # A economia líquida total é a economia de energia menos a variação dos custos de carbono
        total_new_cost = self.new_energy_cost + self.carbon_credits_cost + self.total_compliance_cost
        self.financial_savings = (self.original_energy_cost + original_compliance_cost) - total_new_cost

    def contract_with_plants(self, plants, electricity_price, carbon_price):
        """Negocia com as usinas de pirólise para comprar energia e créditos de carbono."""
        sorted_plants = sorted(
            plants, 
            key=lambda p: ((self.lat - p.lat)**2 + (self.lon - p.lon)**2)**0.5
        )
        
        remaining_demand = self.energy_demand_mwh
        remaining_co2_target = self.co2_emissions_target_t
        
        self.contracted_electricity_mwh = 0.0
        self.purchased_carbon_credits_t = 0.0
        self.new_energy_cost = 0.0
        self.carbon_credits_cost = 0.0
        self.total_decarbonization_achieved_t = 0.0
        
        for plant in sorted_plants:
            if remaining_demand <= 0 and remaining_co2_target <= 0:
                break
                
            # 1. Contrato de Eletricidade
            available_electricity = plant.electricity_generated_mwh
            if available_electricity > 0 and remaining_demand > 0:
                purchased_elec = min(remaining_demand, available_electricity)
                self.contracted_electricity_mwh += purchased_elec
                remaining_demand -= purchased_elec
                self.total_decarbonization_achieved_t += purchased_elec * 0.1
                
            # 2. Compra de Créditos de Carbono (Biocarvão sequestrado)
            available_co2_credits = plant.co2_captured_t
            if available_co2_credits > 0 and remaining_co2_target > 0:
                purchased_credits = min(remaining_co2_target, available_co2_credits)
                self.purchased_carbon_credits_t += purchased_credits
                remaining_co2_target -= purchased_credits
                self.total_decarbonization_achieved_t += purchased_credits

        # Atualiza custos de energia
        self.new_energy_cost = self.contracted_electricity_mwh * electricity_price
        self.new_energy_cost += (self.energy_demand_mwh - self.contracted_electricity_mwh) * 680.0
        self.carbon_credits_cost = self.purchased_carbon_credits_t * carbon_price
        
        self.decarbonization_pct = (self.total_decarbonization_achieved_t / self.co2_emissions_target_t) * 100 if self.co2_emissions_target_t > 0 else 100.0
        self.decarbonization_pct = min(100.0, self.decarbonization_pct)


class MultiAgentSystemEngineSBCEMAS:
    # Classe atualizada com Whirlpool Joinville
    pass

class MultiAgentSystemEngineSBCE:
    """Engine that coordinates agent generation, interaction, and multi-market optimization under the SBCE framework."""
    def __init__(self, collect_rate=0.20, biomass_price=150.0, electricity_price=550.0, sbce_mode="Leilão por Consignação"):
        self.collect_rate = collect_rate
        self.biomass_price = biomass_price
        self.electricity_price = electricity_price
        self.sbce_mode = sbce_mode
        
        # Parâmetros dinâmicos baseados no modo SBCE (alinhados com Guo et al., 2024)
        if sbce_mode == "Alocação Gratuita":
            self.carbon_price = 80.0      # Preço baixo para créditos de biocarvão voluntários
            self.auction_price = 0.0      # Quotas gratuitas
            self.return_coeff = 0.0       # Sem reembolso comercial
            self.subsidy_pct = 0.0        # Sem fundo para usinas
        elif sbce_mode == "Leilão por Consignação":
            self.carbon_price = 120.0     # Valorização dos créditos
            self.auction_price = 100.0    # Preço do leilão regulado
            self.return_coeff = 0.50      # Reembolso de 50% dos leilões de carbono para as indústrias
            self.subsidy_pct = 0.15       # Fundo de fomento subsidia 15% do CAPEX das usinas locais
        elif sbce_mode == "Leilão Tradicional":
            self.carbon_price = 200.0     # Pico de valorização por alta demanda e escassez de quotas
            self.auction_price = 180.0    # Leilão governamental tradicional sem retorno
            self.return_coeff = 0.0       # Sem reembolso para indústrias
            self.subsidy_pct = 0.0        # Fundo vai direto para o caixa público
            
        self.producers = []
        self.plants = []
        self.industries = []
        
        self._initialize_agents()

    def _initialize_agents(self):
        df_sc = get_sc_dataframe()
        
        # 1. Criar Produtores de Biomassa
        for _, row in df_sc.iterrows():
            crop_data = {
                "Arroz": row["Arroz"],
                "Soja": row["Soja"],
                "Milho": row["Milho"],
                "Trigo": row["Trigo"],
                "Feijão": row["Feijão"]
            }
            if sum(crop_data.values()) > 1000:
                p = BiomassProducerAgent(
                    name=f"Produtor_{row['municipio']}",
                    municipality=row["municipio"],
                    region=row["regiao"],
                    lat=row["lat"],
                    lon=row["lon"],
                    crop_data=crop_data
                )
                p.price_per_ton = self.biomass_price
                self.producers.append(p)
                
        # 2. Criar Usinas de Pirólise estrategicamente localizadas
        self.plants = [
            PyrolysisPlantAgent("Usina_Joinville_Pir", "Joinville", -26.30, -48.84, capacity_t_year=12000),
            PyrolysisPlantAgent("Usina_CamposNovos_Pir", "Campos Novos", -27.40, -51.22, capacity_t_year=45000),
            PyrolysisPlantAgent("Usina_Turvo_Pir", "Turvo", -28.92, -49.67, capacity_t_year=25000),
            PyrolysisPlantAgent("Usina_Massaranduba_Pir", "Massaranduba", -26.61, -49.00, capacity_t_year=15000),
            PyrolysisPlantAgent("Usina_Chapeco_Pir", "Chapecó", -27.10, -52.61, capacity_t_year=35000)
        ]
        for plant in self.plants:
            plant.electricity_price = self.electricity_price
            plant.carbon_credit_price = self.carbon_price
            if self.subsidy_pct > 0.0:
                plant.apply_sbce_subsidy(self.subsidy_pct)
            
        # 3. Criar Indústrias Consumidoras
        self.industries = [
            IndustryAgent("Whirlpool_Joinville_Plant", "Joinville", -26.30, -48.84, energy_demand_mwh=35000, co2_emissions_target_t=10000), # Dados reais do Relatório de Sustentabilidade Whirlpool 2024,
            IndustryAgent("Tech_Floripa_Eletro", "Florianópolis", -27.59, -48.54, energy_demand_mwh=5000, co2_emissions_target_t=1200),
            IndustryAgent("Agro_Oeste_Alimentos", "Chapecó", -27.10, -52.61, energy_demand_mwh=25000, co2_emissions_target_t=8500),
            IndustryAgent("Cerâmica_Sul_Revestimentos", "Criciúma", -28.67, -49.37, energy_demand_mwh=18000, co2_emissions_target_t=5500)
        ]

    def run_simulation(self):
        # Passo 1: Produtores calculam biomassa
        for p in self.producers:
            p.calculate_residues(self.collect_rate)
            
        # Passo 2: Usinas compram biomassa
        for plant in self.plants:
            sorted_producers = sorted(
                self.producers,
                key=lambda p_agt: ((plant.lat - p_agt.lat)**2 + (plant.lon - p_agt.lon)**2)**0.5
            )
            
            purchased_biomass = 0.0
            total_purchase_cost = 0.0
            crop_contributions = {"Arroz": 0.0, "Soja": 0.0, "Milho": 0.0, "Trigo": 0.0, "Feijão": 0.0}
            
            for prod in sorted_producers:
                needed_biomass = plant.capacity_t_year - purchased_biomass
                if needed_biomass <= 0:
                    break
                    
                available_from_prod = prod.residues_available_t - prod.sold_biomass_t
                if available_from_prod > 0:
                    bought = prod.sell_biomass(needed_biomass, self.biomass_price)
                    purchased_biomass += bought
                    total_purchase_cost += bought * self.biomass_price
                    
                    total_prod_grain = sum(prod.crop_data.values())
                    if total_prod_grain > 0:
                        for crop in crop_contributions:
                            crop_contributions[crop] += bought * (prod.crop_data[crop] * CROP_PARAMS[crop]["residue_factor"] / total_prod_grain)
            
            crop_mix_proportions = {}
            total_residues_mix = sum(crop_contributions.values())
            if total_residues_mix > 0:
                crop_mix_proportions = {crop: val / total_residues_mix for crop, val in crop_contributions.items()}
            else:
                crop_mix_proportions = {crop: 0.20 for crop in CROP_PARAMS}
                
            plant.run_production(purchased_biomass, crop_mix_proportions)
            plant.calculate_finances(total_purchase_cost)

        # Passo 3: Indústrias negociam e compram contratos de energia e biocarvão
        for ind in self.industries:
            ind.contract_with_plants(self.plants, self.electricity_price, self.carbon_price)
            # Passo 4: Calcula a conformidade e custos regulatórios do SBCE
            ind.calculate_sbce_compliance(self.sbce_mode, self.auction_price, self.return_coeff)

    def get_summary_df(self):
        plant_results = []
        for p in self.plants:
            plant_results.append({
                "Usina": p.name,
                "Localização": p.municipality,
                "Biomassa Processada (t)": p.processed_biomass_t,
                "Eletricidade (MWh)": p.electricity_generated_mwh,
                "Créditos Carbono (tCO2eq)": p.co2_captured_t,
                "Investimento CAPEX": p.capex,
                "Lucro Líquido (R$/ano)": p.net_profit,
                "Payback (Anos)": p.payback_years if p.payback_years != float('inf') else "Inviável"
            })
            
        industry_results = []
        for i in self.industries:
            industry_results.append({
                "Indústria": i.name,
                "Localização": i.municipality,
                "Demanda (MWh)": i.energy_demand_mwh,
                "Meta CO2 (tCO2)": i.co2_emissions_target_t,
                "Eletricidade Contratada (MWh)": i.contracted_electricity_mwh,
                "Créditos Comprados (tCO2eq)": i.purchased_carbon_credits_t,
                "Descarbonização (%)": i.decarbonization_pct,
                "Custos SBCE (R$)": i.total_compliance_cost,
                "Reembolso SBCE (R$)": i.refund_received,
                "Economia Financeira Líquida (R$/ano)": i.financial_savings
            })
            
        return pd.DataFrame(plant_results), pd.DataFrame(industry_results)

if __name__ == "__main__":
    for mode in ["Alocação Gratuita", "Leilão por Consignação", "Leilão Tradicional"]:
        print(f"\n==========================================")
        print(f"SIMULAÇÃO SBCE - MODO: {mode.upper()}")
        print(f"==========================================")
        engine = MultiAgentSystemEngineSBCE(collect_rate=0.20, sbce_mode=mode)
        engine.run_simulation()
        df_plants, df_industries = engine.get_summary_df()
        
        print("\n[USINAS DE PIRÓLISE]")
        print(df_plants[["Usina", "Biomassa Processada (t)", "Lucro Líquido (R$/ano)", "Payback (Anos)"]].to_string(index=False))
        print("\n[INDÚSTRIAS]")
        print(df_industries[["Indústria", "Descarbonização (%)", "Custos SBCE (R$)", "Reembolso SBCE (R$)", "Economia Financeira Líquida (R$/ano)"]].to_string(index=False))
