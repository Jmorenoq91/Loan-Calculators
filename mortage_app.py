import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta
import io
from fpdf import FPDF

# --- Page Config ---
st.set_page_config(page_title="Mortgage Pro 🏠", layout="wide")

# --- Custom CSS for Dark Mode Tiles (Matching Image) ---
st.markdown("""
<style>
    /* Main Background of the app to match the tiles */
    .stApp {
        background-color: #0d1117;
    }

    /* Target the Metric Containers */
    div[data-testid="stMetric"] {
        background-color: #161b22 !important;
        border: 1px solid #30363d !important;
        border-left: 5px solid #00a0e9 !important; /* The Blue Accent Line */
        border-radius: 8px !important;
        padding: 20px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
    }

    /* KPI Labels (MOIC, IRR, etc.) */
    div[data-testid="stMetricLabel"] p {
        color: #8b949e !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }

    /* KPI Values (The Numbers) */
    div[data-testid="stMetricValue"] div {
        color: #ffffff !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
    }

    /* Horizontal line color */
    hr {
        border-top: 1px solid #30363d;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Mortgage Calculator")

# --- Sidebar Inputs in Expander ---
with st.sidebar:
    st.header("🎮 Inputs")
    with st.expander("🛠️ Loan Parameters", expanded=True):
        origination_date = st.date_input("Origination Date", date.today())
        prop_price = st.number_input("Property Price ($)", min_value=0.0, value=100000.0, step=1000.0)
        down_payment_pct = st.slider("Down Payment %", 10, 90, 30)
        annual_interest_rate = st.number_input("Annual Interest Rate (%)", min_value=0.0, value=5.0, step=0.1)
        loan_term_years = st.slider("Loan Term (Years)", 5, 30, 20, step=5)

# --- Financial Calculations ---
down_payment_amt = prop_price * (down_payment_pct / 100)
loan_amount = prop_price - down_payment_amt
monthly_rate = (annual_interest_rate / 100) / 12
number_of_payments = loan_term_years * 12

if monthly_rate > 0:
    monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate)**number_of_payments) / ((1 + monthly_rate)**number_of_payments - 1)
else:
    monthly_payment = loan_amount / number_of_payments

total_paid = monthly_payment * number_of_payments
total_interest = total_paid - loan_amount
ending_date = origination_date + relativedelta(months=number_of_payments)

# --- 1) KPIs (5 Columns) ---
cols = st.columns(4)
cols[0].metric("MONTHLY PMT", f"${monthly_payment:,.2f}")
cols[1].metric("INITIAL LOAN AMT", f"${loan_amount:,.0f}")
cols[2].metric("TOTAL INTEREST", f"${total_interest:,.0f}")
cols[3].metric("TOTAL COST", f"${total_paid:,.0f}")
#cols[4].metric("END DATE", ending_date.strftime("%b %Y"))

st.divider()

# --- Amortization Schedule Data ---
schedule = []
rem_bal = loan_amount
for i in range(1, int(number_of_payments) + 1):
    int_exp = rem_bal * monthly_rate
    cap_amort = monthly_payment - int_exp
    rem_bal -= cap_amort
    schedule.append({
        "Month": i,
        "Payment Date": (origination_date + relativedelta(months=i)).strftime("%Y-%m-%d"),
        "Payment": monthly_payment,
        "Interest Expense": int_exp,
        "Capital Amortization": cap_amort,
        "Ending Balance": max(0, rem_bal)
    })
df_schedule = pd.DataFrame(schedule)

# --- Visualizations ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("📉 Debt Balance")
    st.area_chart(df_schedule.set_index("Payment Date")["Ending Balance"])
with c2:
    st.subheader("📊 Payment Structure")
    st.bar_chart(df_schedule.set_index("Payment Date")[["Capital Amortization", "Interest Expense"]])

# --- Amortization Table ---
st.subheader("📑 Amortization Schedule")
st.dataframe(
    df_schedule.style.format("${:,.2f}", subset=["Payment", "Interest Expense", "Capital Amortization", "Ending Balance"]),
    hide_index=True,
    use_container_width=True
)

# --- PDF Export with Amortization Table ---
def create_pdf(df, price, loan, rate, term, monthly, total_i):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Mortgage Amortization Report", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=10)
    summary = [
        f"Property Price: ${price:,.2f}",
        f"Initial Loan: ${loan:,.2f}",
        f"Interest Rate: {rate}%",
        f"Term: {term} Years",
        f"Monthly Installment: ${monthly:,.2f}",
        f"Total Interest: ${total_i:,.2f}"
    ]
    for row_text in summary:
        pdf.cell(200, 7, row_text, ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 9)
    # Headers
    headers = ["Mo", "Date", "Payment", "Interest", "Principal", "Balance"]
    w = [10, 25, 38, 38, 38, 41]
    for i, h in enumerate(headers):
        pdf.cell(w[i], 10, h, border=1, align='C')
    pdf.ln()
    
    pdf.set_font("Arial", size=8)
    for _, row in df.iterrows():
        pdf.cell(w[0], 7, str(int(row['Month'])), border=1, align='C')
        pdf.cell(w[1], 7, str(row['Payment Date']), border=1, align='C')
        pdf.cell(w[2], 7, f"{row['Payment']:,.2f}", border=1, align='R')
        pdf.cell(w[3], 7, f"{row['Interest Expense']:,.2f}", border=1, align='R')
        pdf.cell(w[4], 7, f"{row['Capital Amortization']:,.2f}", border=1, align='R')
        pdf.cell(w[5], 7, f"{row['Ending Balance']:,.2f}", border=1, align='R')
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# --- Excel Export ---
def to_excel(df, price, loan, rate, term):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        summary_df = pd.DataFrame({"Metric": ["Price", "Loan", "Rate", "Term"], "Value": [price, loan, rate, term]})
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        df.to_excel(writer, sheet_name='Schedule', index=False)
    return output.getvalue()

# --- Export Buttons ---
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Export")
st.sidebar.download_button("📊 Excel", data=to_excel(df_schedule, prop_price, loan_amount, annual_interest_rate, loan_term_years), file_name="mortgage_analysis.xlsx")
st.sidebar.download_button("📄 PDF Report", data=create_pdf(df_schedule, prop_price, loan_amount, annual_interest_rate, loan_term_years, monthly_payment, total_interest), file_name="mortgage_report.pdf")