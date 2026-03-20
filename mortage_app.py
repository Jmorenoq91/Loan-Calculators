import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta
import io
from fpdf import FPDF

# --- Page Config ---
st.set_page_config(page_title="Mortgage Pro 🏠", layout="wide")

# --- Custom CSS for Dark Mode Tiles ---
st.markdown("""
<style>
    .stApp { background-color: #0d1117; }
    div[data-testid="stMetric"] {
        background-color: #161b22 !important;
        border: 1px solid #30363d !important;
        border-left: 5px solid #00a0e9 !important;
        border-radius: 8px !important;
        padding: 20px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
    }
    div[data-testid="stMetricLabel"] p {
        color: #8b949e !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    div[data-testid="stMetricValue"] div {
        color: #ffffff !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
    }
    hr { border-top: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Mortgage Calculator")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("🎮 Inputs")
    with st.expander("🛠️ Loan Parameters", expanded=True):
        origination_date = st.date_input("Origination Date", date.today())
        prop_price = st.number_input("Property Price ($)", min_value=0.0, value=100000.0, step=1000.0)
        down_payment_pct = st.slider("Down Payment %", 10, 90, 20)
        annual_interest_rate = st.number_input("Annual Interest Rate (%)", min_value=0.0, value=5.0, step=0.1)
        loan_term_years = st.slider("Loan Term (Years)", 5, 30, 20, step=5)
        extra_payment = st.number_input("Extra Payment ($)", min_value=0.0, value=0.0, step=10.0)

# --- Logic: Financial Calculations ---
down_payment_amt = prop_price * (down_payment_pct / 100)
loan_amount = prop_price - down_payment_amt
monthly_rate = (annual_interest_rate / 100) / 12
num_months_scheduled = loan_term_years * 12

# Calculate Base Monthly Amortization
if monthly_rate > 0:
    monthly_payment_std = loan_amount * (monthly_rate * (1 + monthly_rate)**num_months_scheduled) / ((1 + monthly_rate)**num_months_scheduled - 1)
else:
    monthly_payment_std = loan_amount / num_months_scheduled

# --- Logic: Amortization Schedule Generation ---
schedule = []
rem_bal = loan_amount

for i in range(1, int(num_months_scheduled) + 1):
    int_exp = rem_bal * monthly_rate
    # Ensure payment doesn't exceed balance + interest
    realized_payment = min(monthly_payment_std + extra_payment, rem_bal + int_exp)
    cap_amort = realized_payment - int_exp
    rem_bal -= cap_amort
    
    pay_date = origination_date + relativedelta(months=i)
    
    schedule.append({
        "Month": i,
        "Payment Date": pay_date,
        "Payment": realized_payment,
        "Interest Expense": int_exp,
        "Capital Amortization": cap_amort,
        "Ending Balance": max(0, rem_bal)
    })
    
    if rem_bal <= 0.01: # Small epsilon for float precision
        break

df_schedule = pd.DataFrame(schedule)

# --- Logic: Post-Loop Dynamic KPIs ---
total_interest = df_schedule["Interest Expense"].sum()
total_paid = df_schedule["Payment"].sum()
actual_end_date = df_schedule["Payment Date"].iloc[-1]

# --- 1) KPI Display (2x3 Layout) ---
r1_col1, r1_col2, r1_col3 = st.columns(3)
r1_col1.metric("DOWN PAYMENT", f"${down_payment_amt:,.0f}")
r1_col2.metric("MONTHLY PAYMENT", f"${min(monthly_payment_std + extra_payment, loan_amount * (1 + monthly_rate)):,.2f}")
r1_col3.metric("END DATE", actual_end_date.strftime("%b %Y"))

r2_col1, r2_col2, r2_col3 = st.columns(3)
r2_col1.metric("LOAN AMOUNT", f"${loan_amount:,.0f}")
r2_col2.metric("TOTAL INTEREST", f"${total_interest:,.0f}")
r2_col3.metric("TOTAL COST", f"${total_paid:,.0f}")

st.divider()

# --- Visualizations ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("📉 Debt Balance Over Time")
    chart_df = df_schedule.copy()
    
    # 1. Convert to pandas datetime first
    chart_df["Payment Date"] = pd.to_datetime(chart_df["Payment Date"])
    
    # 2. Now you can use .dt safely
    chart_df["Date"] = chart_df["Payment Date"].dt.strftime("%Y-%m-%d")
    
    st.area_chart(chart_df.set_index("Date")["Ending Balance"])

with c2:
    st.subheader("📊 Payment Structure")
    st.bar_chart(chart_df.set_index("Date")[["Capital Amortization", "Interest Expense"]])


# --- Amortization Table ---
st.subheader("📑 Full Amortization Schedule")
st.dataframe(
    df_schedule.style.format({
        "Payment Date": lambda x: x.strftime("%Y-%m-%d"),
        "Payment": "${:,.2f}", 
        "Interest Expense": "${:,.2f}", 
        "Capital Amortization": "${:,.2f}", 
        "Ending Balance": "${:,.2f}"
    }),
    hide_index=True,
    use_container_width=True
)

# --- Export Helpers ---
def create_pdf(df, price, loan, rate, term, monthly, total_i, end_date):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Mortgage Amortization Report", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=10)
    summary = [
        f"Property Price: ${price:,.2f}",
        f"Initial Loan: ${loan:,.2f}",
        f"Interest Rate: {rate}%",
        f"Term: {term} Years",
        f"Total Monthly Outflow: ${monthly:,.2f}",
        f"Total Interest Paid: ${total_i:,.2f}",
        f"Payoff Date: {end_date.strftime('%b %Y')}"
    ]
    for text in summary:
        pdf.cell(200, 7, text, ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    headers = ["Mo", "Date", "Payment", "Interest", "Principal", "Balance"]
    widths = [10, 25, 38, 38, 38, 41]
    
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 10, h, border=1, align='C')
    pdf.ln()
    
    pdf.set_font("Arial", size=8)
    for _, row in df.iterrows():
        pdf.cell(widths[0], 7, str(int(row['Month'])), border=1, align='C')
        pdf.cell(widths[1], 7, row['Payment Date'].strftime("%Y-%m-%d"), border=1, align='C')
        pdf.cell(widths[2], 7, f"{row['Payment']:,.2f}", border=1, align='R')
        pdf.cell(widths[3], 7, f"{row['Interest Expense']:,.2f}", border=1, align='R')
        pdf.cell(widths[4], 7, f"{row['Capital Amortization']:,.2f}", border=1, align='R')
        pdf.cell(widths[5], 7, f"{row['Ending Balance']:,.2f}", border=1, align='R')
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Schedule', index=False)
    return output.getvalue()

# --- Sidebar Export Buttons ---
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Export")

pdf_bytes = create_pdf(df_schedule, prop_price, loan_amount, annual_interest_rate, loan_term_years, (monthly_payment_std + extra_payment), total_interest, actual_end_date)
st.sidebar.download_button("📄 PDF Report", data=pdf_bytes, file_name="mortgage_report.pdf", mime="application/pdf")

excel_bytes = to_excel(df_schedule)
st.sidebar.download_button("📊 Excel Schedule", data=excel_bytes, file_name="mortgage_analysis.xlsx")
