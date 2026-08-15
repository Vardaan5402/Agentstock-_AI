import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import streamlit as st

def create_simulation_timeline_chart(
    simulations: list,
    current_stock: float,
    daily_demand: float,
    safety_stock: float,
    horizon_days: int = 14,
    supplier_names: dict[str, str] | None = None,
):
    """Create a Plotly timeline chart using exact mathematical simulation trajectories."""
    fig = go.Figure()
    names_map = supplier_names or {}
    
    # Add safety stock line
    fig.add_trace(go.Scatter(
        x=[0, horizon_days],
        y=[safety_stock, safety_stock],
        mode='lines',
        name='Safety Stock Threshold',
        line=dict(color='#EF4444', width=2, dash='dash')
    ))

    colors = [
        '#F59E0B',  # Amber
        '#22C55E',  # Green
        '#00D4FF',  # Cyan
        '#A78BFA',  # Purple
        '#EC4899',  # Pink
    ]

    for idx, sim in enumerate(simulations):
        scenario_id = sim.scenario_id
        color = colors[idx % len(colors)]
        
        if scenario_id == 'DO_NOTHING':
            action_name = 'Do Nothing (No Order)'
        else:
            sup_id = sim.supplier_id or scenario_id.replace('PURCHASE_', '')
            friendly_name = names_map.get(sup_id, sup_id)
            if friendly_name.startswith('workbench-supplier-'):
                friendly_name = friendly_name.replace('workbench-supplier-', 'Supplier ')
            action_name = f"Order via {friendly_name}"

        # Extract EXACT mathematical inventory trajectory from simulation engine
        if sim.inventory_trajectory:
            days = [0] + [point.day + 1 for point in sim.inventory_trajectory]
            stock_path = [current_stock] + [point.ending_inventory for point in sim.inventory_trajectory]
        else:
            days = list(range(horizon_days + 1))
            stock_path = [max(0, current_stock - (d * daily_demand)) for d in days]
            
        fig.add_trace(go.Scatter(
            x=days,
            y=stock_path,
            mode='lines+markers',
            name=action_name,
            line=dict(color=color, width=3),
            marker=dict(size=5)
        ))

    fig.update_layout(
        title=dict(text="<b>Projected Daily Inventory Trajectory</b>", font=dict(color='#FFFFFF', size=15)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(13, 20, 34, 0.6)',
        xaxis=dict(
            title="Days into Future",
            gridcolor='rgba(255, 255, 255, 0.08)',
            color='#94A3B8',
            dtick=1
        ),
        yaxis=dict(
            title="Projected Stock (Units)",
            gridcolor='rgba(255, 255, 255, 0.08)',
            color='#94A3B8'
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='#CBD5E1', size=11)
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        height=360,
    )
    
    return fig


def create_supplier_comparison_chart(
    purchase_options: list,
    supplier_names: dict[str, str] | None = None
):
    """Create a Plotly bar chart comparing Supplier Cost vs Lead Time with bar labels and feasibility diagnostics."""
    if not purchase_options:
        return None
        
    names_map = supplier_names or {}
    data = []
    for opt in purchase_options:
        raw_name = names_map.get(opt.supplier_id, opt.supplier_id)
        if raw_name.startswith('workbench-supplier-') or len(raw_name) > 20:
            raw_name = raw_name.replace('workbench-supplier-', 'Supplier ')
        
        # Display text on bar
        if opt.total_cost > 0:
            bar_text = f"₹{opt.total_cost:,.0f}"
        else:
            bar_text = "₹0 (Stock Safe)"
            
        data.append({
            'Supplier': raw_name,
            'Total Cost (₹)': opt.total_cost,
            'Bar Label': bar_text,
            'Lead Time (Days)': opt.supplier_lead_time_days,
            'Order Qty': opt.purchase_quantity,
            'Unit Price (₹)': opt.unit_price,
            'Reliability (%)': f"{opt.supplier_reliability * 100:.0f}%",
            'Status': 'Feasible' if opt.feasible else 'Infeasible',
            'Reason': opt.reason or ('Feasible' if opt.feasible else 'Constraint breached')
        })
        
    df = pd.DataFrame(data)
    
    fig = px.bar(
        df,
        x='Supplier',
        y='Total Cost (₹)',
        color='Status',
        text='Bar Label',
        color_discrete_map={'Feasible': '#22C55E', 'Infeasible': '#EF4444'},
        hover_data=['Lead Time (Days)', 'Order Qty', 'Unit Price (₹)', 'Reliability (%)', 'Reason'],
        title="<b>Supplier Total Cost Comparison</b>"
    )
    
    fig.update_traces(
        textposition='outside',
        textfont=dict(color='#FFFFFF', size=11),
        cliponaxis=False,
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(13, 20, 34, 0.6)',
        font=dict(color='#CBD5E1'),
        xaxis=dict(gridcolor='rgba(255, 255, 255, 0.08)', color='#94A3B8', title=""),
        yaxis=dict(
            gridcolor='rgba(255, 255, 255, 0.08)',
            color='#94A3B8',
            title="Total Cost (₹)",
            range=[0, max(100, df['Total Cost (₹)'].max() * 1.25)]  # Ensure room for bar labels
        ),
        legend=dict(font=dict(color='#CBD5E1', size=11)),
        margin=dict(l=30, r=30, t=45, b=30),
        height=320,
    )
    
    return fig


def create_runway_gauge_chart(runway_days: float | None, lead_time_days: float):
    """Create a Plotly gauge chart for inventory runway days."""
    val = runway_days if runway_days is not None else 0
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number={'suffix': " Days", 'font': {'color': "#FFFFFF", 'size': 24}},
        title={'text': "<b>Inventory Runway</b>", 'font': {'color': "#94A3B8", 'size': 14}},
        gauge={
            'axis': {'range': [0, max(15, val + 2)], 'tickwidth': 1, 'tickcolor': "#94A3B8"},
            'bar': {'color': "#6D5DFC"},
            'bgcolor': "rgba(13, 20, 34, 0.8)",
            'bordercolor': "rgba(255, 255, 255, 0.1)",
            'steps': [
                {'range': [0, 2], 'color': 'rgba(239, 68, 68, 0.4)'},
                {'range': [2, lead_time_days], 'color': 'rgba(245, 158, 11, 0.4)'},
                {'range': [lead_time_days, 15], 'color': 'rgba(34, 197, 94, 0.4)'}
            ],
            'threshold': {
                'line': {'color': "#00D4FF", 'width': 3},
                'thickness': 0.75,
                'value': lead_time_days
            }
        }
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#CBD5E1'),
        margin=dict(l=20, r=20, t=30, b=20),
        height=220,
    )
    return fig
