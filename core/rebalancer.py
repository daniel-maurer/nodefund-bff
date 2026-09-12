"""
Motor de Cálculo para a Calculadora de Rebalanceamento.
Calcula o valor exato a aportar em cada ativo para aproximar a carteira da meta ideal,
respeitando estritamente o Valor Mínimo de Movimentação (tíquete mínimo) de cada produto.
"""

from typing import Dict, List, Any
from .storage import clean_cnpj, format_cnpj, clean_ticker

def get_asset_code(f: Dict[str, Any]) -> str:
    a_type = f.get("type", "fund")
    if a_type == "b3":
        return clean_ticker(f.get("code") or f.get("id") or "")
    c = clean_cnpj(f.get("cnpj") or f.get("code") or "")
    if not c:
        return clean_ticker(f.get("code") or f.get("id") or "")
    return c

def calculate_rebalance_orders(
    portfolio: Dict[str, Any],
    current_balances: Dict[str, float],
    contribution: float
) -> Dict[str, Any]:
    """
    Calcula as ordens de aporte para rebalanceamento.
    
    portfolio: dicionário com a lista de fundos/ativos da carteira cadastrada
    current_balances: dicionário {codigo_ou_cnpj: saldo_atual_em_reais}
    contribution: valor do novo aporte em reais (>= 0)
    """
    funds = portfolio.get("funds", [])
    if not funds:
        return {"error": "A carteira não possui ativos cadastrados."}

    # Normalizar chaves dos saldos atuais (aceita CNPJ, ticker ou ID)
    clean_balances = {}
    for k, val in current_balances.items():
        try:
            v = max(0.0, float(val))
            k_str = str(k).strip()
            clean_balances[k_str] = v
            clean_balances[clean_cnpj(k_str)] = v
            clean_balances[clean_ticker(k_str)] = v
        except (ValueError, TypeError):
            pass

    # Normalizar pesos
    total_pct = sum(float(f.get("target_pct", 0.0)) for f in funds)
    if total_pct <= 0:
        return {"error": "A soma dos percentuais da carteira deve ser maior que zero."}

    # Preparar lista estruturada de ativos
    items = []
    total_current_balance = 0.0

    for f in funds:
        a_type = f.get("type", "fund")
        code = get_asset_code(f)
        curr_bal = (
            clean_balances.get(code) or
            clean_balances.get(f.get("id")) or
            clean_balances.get(f.get("code")) or
            clean_balances.get(f.get("cnpj")) or
            0.0
        )
        target_w = float(f.get("target_pct", 0.0)) / total_pct
        min_ticket = float(f.get("min_investment", 100.0))
        
        display_code = format_cnpj(code) if (a_type == "fund" and len(code) == 14) else code
        
        total_current_balance += curr_bal
        items.append({
            "id": f.get("id", code),
            "name": f.get("name", "Ativo"),
            "type": a_type,
            "cnpj": display_code,
            "code": display_code,
            "cnpj_clean": code,
            "target_pct": float(f.get("target_pct", 0.0)),
            "target_w": target_w,
            "min_investment": min_ticket,
            "current_balance": curr_bal,
            "color": f.get("color", "#3b82f6")
        })

    total_projected_balance = total_current_balance + contribution

    # Calcular metas e déficits ideais
    for item in items:
        target_val = total_projected_balance * item["target_w"]
        deficit = target_val - item["current_balance"]
        item["target_value"] = target_val
        item["raw_deficit"] = deficit
        item["is_underweight"] = deficit > 0.001
        item["current_pct"] = (item["current_balance"] / total_current_balance * 100.0) if total_current_balance > 0 else 0.0

    # Algoritmo de Alocação com Tíquete Mínimo
    # Se aporte <= 0, nenhuma alocação
    allocations = {item["cnpj_clean"]: 0.0 for item in items}
    
    if contribution > 0:
        underweight_items = [it for it in items if it["is_underweight"]]
        
        # Se nenhum fundo estiver abaixo da meta (carteira já 100% equilibrada ou aporte cobre tudo)
        if not underweight_items:
            underweight_items = list(items)

        # Ordenar ativos subponderados por déficit decrescente
        underweight_items.sort(key=lambda x: x["raw_deficit"], reverse=True)

        # Testar se o aporte mínimo global pode ser atendido
        min_possible_ticket = min(it["min_investment"] for it in items)
        
        if contribution < min_possible_ticket:
            # Aporte é menor que o menor tíquete de qualquer fundo
            pass
        else:
            # Algoritmo de distribuição inteligente:
            # 1. Tentar alocação proporcional aos déficits
            sum_deficits = sum(max(0.0, it["raw_deficit"]) for it in underweight_items)
            
            # Subconjunto de fundos que podem receber aporte respeitando tíquete mínimo
            # Testamos alocações válidas
            # Estratégia de priorização gulosa (Greedy) que garante respeito ao tíquete mínimo
            remaining_cash = round(contribution, 2)
            
            # Passo 1: Determinar quais fundos são prioritários
            # Ordenamos por maior déficit absoluto
            eligible_funds = [it for it in underweight_items if it["min_investment"] <= remaining_cash]
            
            if eligible_funds:
                # Calcular proposta ideal contínua para os elegíveis
                sub_sum_def = sum(it["raw_deficit"] for it in eligible_funds)
                if sub_sum_def <= 0:
                    sub_sum_def = sum(it["target_w"] for it in eligible_funds)
                    raw_proposals = {it["cnpj_clean"]: remaining_cash * (it["target_w"] / sub_sum_def) for it in eligible_funds}
                else:
                    raw_proposals = {it["cnpj_clean"]: remaining_cash * (it["raw_deficit"] / sub_sum_def) for it in eligible_funds}
                
                # Ajustar para respeitar os tíquetes mínimos
                # Aqueles cuja proposta < min_investment:
                # Precisam ser elevados a min_investment ou descartados
                accepted = {}
                pending = list(eligible_funds)
                
                while pending:
                    # Recalcular propostas para os pendentes com o saldo restante
                    curr_sum_def = sum(it["raw_deficit"] for it in pending)
                    if curr_sum_def <= 0:
                        props = {it["cnpj_clean"]: remaining_cash / len(pending) for it in pending}
                    else:
                        props = {it["cnpj_clean"]: remaining_cash * (it["raw_deficit"] / curr_sum_def) for it in pending}
                    
                    # Verificar se todos atendem ao tíquete mínimo
                    all_meet_min = True
                    for it in pending:
                        c_id = it["cnpj_clean"]
                        if props[c_id] < it["min_investment"]:
                            all_meet_min = False
                            break
                            
                    if all_meet_min:
                        # Todos atendem! Atribuir
                        for it in pending:
                            accepted[it["cnpj_clean"]] = round(props[it["cnpj_clean"]], 2)
                        remaining_cash = 0.0
                        break
                    else:
                        # O fundo com menor proposta que não atinge seu tíquete é removido da rodada
                        # para concentrar recursos nos ativos mais deficientes
                        failing = [it for it in pending if props[it["cnpj_clean"]] < it["min_investment"]]
                        # Remove o de menor déficit
                        failing.sort(key=lambda x: x["raw_deficit"])
                        removed_fund = failing[0]
                        pending.remove(removed_fund)
                        accepted[removed_fund["cnpj_clean"]] = 0.0

                # Se sobrou algum saldo por arredondamento, adiciona ao fundo mais deficitário aceito
                total_accepted = sum(accepted.values())
                leftover = round(contribution - total_accepted, 2)
                
                if leftover > 0.01:
                    # Encontrar o fundo aceito com maior déficit
                    accepted_funds = [it for it in eligible_funds if accepted.get(it["cnpj_clean"], 0) > 0]
                    if accepted_funds:
                        best_fund = max(accepted_funds, key=lambda x: x["raw_deficit"])
                        accepted[best_fund["cnpj_clean"]] = round(accepted[best_fund["cnpj_clean"]] + leftover, 2)
                    elif eligible_funds:
                        # Se nenhum foi aceito no rateio conjunto, aloca tudo no mais necessitado se ele aceitar
                        top_fund = eligible_funds[0]
                        if contribution >= top_fund["min_investment"]:
                            accepted[top_fund["cnpj_clean"]] = round(contribution, 2)

                for c_clean, amt in accepted.items():
                    allocations[c_clean] = amt

    # Montar resposta detalhada com ordens
    orders = []
    total_allocated = 0.0

    for item in items:
        c_clean = item["cnpj_clean"]
        alloc_amt = allocations.get(c_clean, 0.0)
        total_allocated += alloc_amt
        new_bal = item["current_balance"] + alloc_amt
        new_pct = (new_bal / total_projected_balance * 100.0) if total_projected_balance > 0 else 0.0
        
        dev_before = item["current_pct"] - item["target_pct"]
        dev_after = new_pct - item["target_pct"]

        # Definir status e ação
        if alloc_amt > 0:
            action = "APLICAR"
            status_msg = f"Aplicar R$ {alloc_amt:,.2f} (mínimo: R$ {item['min_investment']:,.2f})"
        else:
            if item["is_underweight"]:
                if contribution < item["min_investment"]:
                    action = "TÍQUETE_INSUFICIENTE"
                    status_msg = f"Abaixo do tíquete mínimo (R$ {item['min_investment']:,.2f})"
                else:
                    action = "PRIORIZADO_OUTRO"
                    status_msg = "Aporte priorizado em ativo com maior defasagem"
            else:
                action = "MANTER"
                status_msg = "Ativo já alinhado ou acima da meta"

        orders.append({
            "id": item["id"],
            "name": item["name"],
            "cnpj": item["cnpj"],
            "cnpj_clean": c_clean,
            "target_pct": round(item["target_pct"], 2),
            "min_investment": round(item["min_investment"], 2),
            "current_balance": round(item["current_balance"], 2),
            "current_pct": round(item["current_pct"], 2),
            "suggested_contribution": round(alloc_amt, 2),
            "new_balance": round(new_bal, 2),
            "new_pct": round(new_pct, 2),
            "deviation_before": round(dev_before, 2),
            "deviation_after": round(dev_after, 2),
            "action": action,
            "status_message": status_msg,
            "color": item["color"]
        })

    # Ordenar ordens colocando as de "APLICAR" no topo, ordenadas por valor decrescente
    orders.sort(key=lambda x: (0 if x["action"] == "APLICAR" else 1, -x["suggested_contribution"]))

    unallocated = round(max(0.0, contribution - total_allocated), 2)

    return {
        "total_current_balance": round(total_current_balance, 2),
        "contribution": round(contribution, 2),
        "total_projected_balance": round(total_projected_balance, 2),
        "total_allocated": round(total_allocated, 2),
        "unallocated_cash": unallocated,
        "orders": orders
    }
