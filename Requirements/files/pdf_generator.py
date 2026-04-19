import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
import json


def _clean(text: str) -> str:
    """Elimina markdown y emojis para que ReportLab pueda renderizarlo."""
    # Quitar encabezados markdown
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Quitar negrita/cursiva
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    # Quitar backticks
    text = re.sub(r'`+', '', text)
    # Quitar separadores de tabla |---|
    text = re.sub(r'\|[-:| ]+\|', '', text)
    # Quitar pipes de tabla
    text = re.sub(r'\|', ' ', text)
    # Quitar emojis y caracteres fuera del rango Latin-1
    text = re.sub(r'[^\x00-\xFF]', '', text)
    # Limpiar espacios múltiples y líneas en blanco extra
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

class PDFReportGenerator:
    """Generador de reportes PDF para el trading bot"""
    
    def __init__(self, filename: str = None):
        if filename is None:
            filename = f"trading_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        self.filename = filename
        self.story = []
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configura estilos personalizados"""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        self.heading_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#283593'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
    
    def add_title(self, title: str):
        """Añade título al reporte"""
        self.story.append(Paragraph(title, self.title_style))
        self.story.append(Spacer(1, 0.2*inch))
        
        # Fecha y hora
        timestamp = datetime.now().strftime("%d de %B de %Y a las %H:%M")
        self.story.append(Paragraph(f"<i>Generado: {timestamp}</i>", self.styles['Normal']))
        self.story.append(Spacer(1, 0.3*inch))
    
    def add_portfolio_summary(self, positions: dict):
        """Añade resumen de cartera"""
        self.story.append(Paragraph("Resumen de Cartera", self.heading_style))
        
        # Calcular totales
        total_value = 0
        total_invested = 0
        
        data = [["Símbolo", "Cantidad", "Precio Entrada", "Precio Actual", "Valor", "P&L %"]]
        
        for symbol, pos in positions.items():
            current_value = pos.get('quantity', 0) * pos.get('current_price', 0)
            entry_cost = pos.get('quantity', 0) * pos.get('entry_price', 0)
            pnl_percent = ((current_value - entry_cost) / entry_cost * 100) if entry_cost > 0 else 0
            
            total_value += current_value
            total_invested += entry_cost
            
            pnl_color = colors.green if pnl_percent > 0 else colors.red
            
            data.append([
                symbol,
                f"{pos.get('quantity', 0):.4f}",
                f"${pos.get('entry_price', 0):.2f}",
                f"${pos.get('current_price', 0):.2f}",
                f"${current_value:,.2f}",
                f"{pnl_percent:+.2f}%"
            ])
        
        # Fila de totales
        total_pnl_percent = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
        data.append([
            "TOTAL",
            "",
            f"${total_invested:,.2f}",
            "",
            f"${total_value:,.2f}",
            f"{total_pnl_percent:+.2f}%"
        ])
        
        table = Table(data, colWidths=[1*inch, 1*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8eaf6')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f5f5')])
        ]))
        
        self.story.append(table)
        self.story.append(Spacer(1, 0.3*inch))
    
    def add_news_analysis(self, news_items: list, ai_analysis: str):
        """Añade análisis de noticias"""
        self.story.append(Paragraph("Noticias y Analisis", self.heading_style))
        
        # Noticias
        for i, news in enumerate(news_items[:5], 1):  # Top 5
            title = f"{i}. {news.get('title', 'Sin título')}"
            self.story.append(Paragraph(f"<b>{title}</b>", self.styles['Normal']))
            self.story.append(Paragraph(
                f"<font size=9><i>Fuente: {news.get('source', 'Unknown')}</i></font>",
                self.styles['Normal']
            ))
            url = news.get('url', '')
            if url:
                self.story.append(Paragraph(
                    f'<font size=8 color="blue"><u><a href="{url}">{url[:80]}</a></u></font>',
                    self.styles['Normal']
                ))
            self.story.append(Spacer(1, 0.1*inch))
        
        self.story.append(Spacer(1, 0.2*inch))
        
        # Análisis IA
        self.story.append(Paragraph("Analisis IA", self.styles['Heading3']))
        for block in _clean(ai_analysis).split('\n\n'):
            block = block.strip()
            if block:
                self.story.append(Paragraph(block, self.styles['Normal']))
                self.story.append(Spacer(1, 0.08*inch))
        self.story.append(Spacer(1, 0.2*inch))
    
    def add_trading_signals(self, signals: list):
        """Añade señales de trading"""
        self.story.append(Paragraph("Senales de Trading", self.heading_style))
        
        data = [["Símbolo", "Acción", "Confianza", "Precio Objetivo", "Stop Loss"]]
        
        for signal in signals:
            action_color = {
                "BUY": colors.green,
                "SELL": colors.red,
                "HOLD": colors.grey
            }.get(signal.get('action', 'HOLD'), colors.grey)
            
            data.append([
                signal.get('symbol', '?'),
                signal.get('action', 'HOLD'),
                f"{signal.get('confidence', 0)}%",
                f"${signal.get('target_price', '?')}",
                f"${signal.get('stop_loss', '?')}"
            ])
        
        table = Table(data, colWidths=[1*inch, 1*inch, 1*inch, 1.2*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
        ]))
        
        self.story.append(table)
        self.story.append(Spacer(1, 0.3*inch))
    
    def add_ai_accuracy(self, stats: dict):
        """Sección de precisión histórica del feedback loop IA."""
        self.story.append(Paragraph("Precision Historica de Senales IA", self.heading_style))

        accuracy = stats.get("accuracy_pct", 0)
        color = colors.HexColor("#22c55e") if accuracy >= 55 else (
            colors.HexColor("#f59e0b") if accuracy >= 45 else colors.HexColor("#ef4444")
        )

        summary = (
            f"Senales evaluadas: {stats['total']}   |   "
            f"Correctas: {stats['correct']}   |   "
            f"Precision global: {accuracy}%"
        )
        style = ParagraphStyle(
            "AccuracySummary", parent=self.styles["Normal"],
            fontSize=11, textColor=color, fontName="Helvetica-Bold", spaceAfter=8,
        )
        self.story.append(Paragraph(summary, style))

        by_sym = stats.get("by_symbol", {})
        if by_sym:
            data = [["Activo", "Precision %", "P&L Promedio %", "Evaluaciones"]]
            for sym, d in by_sym.items():
                data.append([
                    sym,
                    f"{d['accuracy_pct']}%",
                    f"{d['avg_pnl_pct']:+.2f}%",
                    str(stats["total"]),
                ])
            table = Table(data, colWidths=[1.2*inch, 1.2*inch, 1.5*inch, 1.2*inch])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]))
            self.story.append(table)

        self.story.append(Spacer(1, 0.3*inch))

    def add_risk_assessment(self, risk_data: dict):
        """Añade evaluación de riesgo"""
        self.story.append(Paragraph("Evaluacion de Riesgo", self.heading_style))
        
        analysis = _clean(risk_data.get('analysis', ''))
        for block in (analysis.split('\n\n') if analysis else ['Sin datos de riesgo.']):
            block = block.strip()
            if block:
                self.story.append(Paragraph(block, self.styles['Normal']))
                self.story.append(Spacer(1, 0.08*inch))
        self.story.append(Spacer(1, 0.3*inch))
    
    def add_recommendations(self, recommendations: list):
        """Añade recomendaciones"""
        self.story.append(Paragraph("Recomendaciones", self.heading_style))
        
        for rec in recommendations:
            self.story.append(Paragraph(f"- {_clean(rec)}", self.styles['Normal']))
        
        self.story.append(Spacer(1, 0.3*inch))
    
    def add_disclaimer(self):
        """Añade aviso legal"""
        disclaimer = """
        <font size=8 color="grey">
        <b>AVISO LEGAL:</b> Este reporte es generado automáticamente por un bot de trading con IA.
        No constituye asesoramiento financiero profesional. Las predicciones son basadas en datos
        históricos y modelos estadísticos, que no garantizan resultados futuros. Invierte bajo
        tu propio riesgo. Consulta a un asesor financiero certificado antes de tomar decisiones.
        </font>
        """
        self.story.append(Paragraph(disclaimer, self.styles['Normal']))
    
    def generate(self):
        """Genera el PDF"""
        doc = SimpleDocTemplate(
            self.filename,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
        )
        
        doc.build(self.story)
        return self.filename

# ============= EJEMPLO DE USO =============
if __name__ == "__main__":
    # Datos de ejemplo
    positions = {
        "BTC": {
            "quantity": 0.5,
            "entry_price": 45000,
            "current_price": 48500
        },
        "ETH": {
            "quantity": 3.0,
            "entry_price": 2500,
            "current_price": 2650
        },
        "AAPL": {
            "quantity": 100,
            "entry_price": 180,
            "current_price": 195
        }
    }
    
    news_items = [
        {
            "source": "Reuters",
            "title": "Fed mantiene tasas",
            "description": "La FED decide mantener tasa de interés en 5.25-5.50%"
        },
        {
            "source": "Bloomberg",
            "title": "Apple rompe récord de ventas",
            "description": "Apple reporta récord de ventas en Q4 2024"
        }
    ]
    
    signals = [
        {
            "symbol": "BTC",
            "action": "BUY",
            "confidence": 75,
            "target_price": 50000,
            "stop_loss": 46000
        }
    ]
    
    risk_data = {
        "systematic": "Moderate",
        "specific": "Low",
        "volatility": "18.5"
    }
    
    recommendations = [
        "Rebalancear cartera hacia crypto (actualmente 30%)",
        "Considerar vender AAPL con ganancias (+8.3%)",
        "Agregar 10% a BTC si rompe 49k"
    ]
    
    # Generar reporte
    report = PDFReportGenerator()
    report.add_title("📈 Reporte de Trading Diario")
    report.add_portfolio_summary(positions)
    report.add_news_analysis(news_items, "Las noticias son positivas para tech stocks...")
    report.add_trading_signals(signals)
    report.add_risk_assessment(risk_data)
    report.add_recommendations(recommendations)
    report.add_disclaimer()
    report.generate()
