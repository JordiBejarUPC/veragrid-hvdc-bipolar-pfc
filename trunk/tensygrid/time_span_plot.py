import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os


def generar_plot_final_amb_etiquetes(nom_fitxer='time_span.md'):
    if not os.path.exists(nom_fitxer):
        print(f"Error: No s'ha trobat el fitxer '{nom_fitxer}'")
        return

    dades = []
    with open(nom_fitxer, 'r', encoding='utf-8') as f:
        for linia in f:
            if '|' in linia and '---' not in linia:
                cols = [c.strip() for c in linia.split('|')]
                cols = [c for c in cols if c != '']

                grid_name = ""
                t_zero = None
                t_pre = None

                extensions = ['.gridcal', '.xlsx', '.veragrid', '.json', '.xml', '.ods', '.dgs', '.md']

                for i, c in enumerate(cols):
                    if any(ext in c.lower() for ext in extensions):
                        grid_name = c
                        if i + 1 < len(cols):
                            t_zero = pd.to_numeric(cols[i + 1], errors='coerce')
                        if i + 2 < len(cols):
                            t_pre = pd.to_numeric(cols[i + 2], errors='coerce')
                        break

                if grid_name:
                    dades.append({'Grid': grid_name, 'T_zero': t_zero, 'T_pre': t_pre})

    if not dades:
        print("No s'han trobat dades vàlides.")
        return

    df = pd.DataFrame(dades)

    # Alçada dinàmica: 0.4 polzades per fila per donar espai a les etiquetes de text
    alcada = max(10, len(df) * 0.4)
    fig, ax = plt.subplots(figsize=(14, alcada))

    y_pos = np.arange(len(df))
    width = 0.35

    # Barres
    barres_zero = ax.barh(y_pos + width / 2, df['T_zero'], width, label='Temps des de zero (s)', color='red')
    barres_pre = ax.barh(y_pos - width / 2, df['T_pre'], width, label='Temps precomputat (s)', color='royalblue')

    # Afegir els valors de temps al costat de cada barra
    def afegir_etiquetes(rects):
        for rect in rects:
            width = rect.get_width()
            if not np.isnan(width):  # Només si hi ha dades
                ax.annotate(f'{width:.2f}s',
                            xy=(width, rect.get_y() + rect.get_height() / 2),
                            xytext=(5, 0),  # 5 punts de desplaçament a la dreta
                            textcoords="offset points",
                            ha='left', va='center', fontsize=8)

    afegir_etiquetes(barres_zero)
    afegir_etiquetes(barres_pre)

    # Configuració d'eixos
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df['Grid'], fontsize=9)
    ax.invert_yaxis()  # De dalt a baix

    ax.set_xlabel('Temps (segons)')
    ax.set_title('Comparativa d\'Execució: time_span.md', pad=20, fontsize=14)

    # Llegenda a la part superior dreta
    ax.legend(loc='upper right', frameon=True, shadow=True)

    # Grid vertical per ajudar a llegir els segons
    ax.grid(axis='x', linestyle='--', alpha=0.4)

    # Donar espai extra a la dreta perquè el text dels segons no quedi tallat
    ax.set_xlim(0, df[['T_zero', 'T_pre']].max().max() * 1.15)

    plt.tight_layout()
    plt.savefig('grafic_time_span_detallat.png', dpi=300)
    print(f"Gràfic generat: 'grafic_time_span_detallat.png'")
    plt.show()


# Execució
generar_plot_final_amb_etiquetes('time_span.md')