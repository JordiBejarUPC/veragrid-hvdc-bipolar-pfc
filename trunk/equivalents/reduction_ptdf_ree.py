#!/usr/bin/env python
# coding: utf-8

# In[1]:


import VeraGridEngine as vge
import numpy as np

# In[2]:


path = r"case300.raw"
# path = r"case118.raw"


# In[3]:


grid = vge.open_file(path)

# ## Initial Power flow

# In[ ]:


res = vge.linear_power_flow(grid)

# In[ ]:


Fp = res.get_branch_df()['Pf'].to_numpy()
Fp.shape

# In[ ]:


PTDF_full = res.mdl(vge.ResultTypes.PTDF).to_df().to_numpy()
PTDF_full.shape

# La ecuación de un sistema lineal se expresa como:
# 
# $$
# PTDFx = Fp
# $$
# 
# donde:
# 
# - \( PTDF \) es la matriz PTDF completa (Todos los nudos)
# - \( x \) es el vector de generación,
# - \( b \) es el vector de flujos por las ramas.
# 

# In[ ]:


generacion_inicial, residuals, rank, s = np.linalg.lstsq(PTDF_full, Fp, rcond=None)[0]
generacion_inicial.shape

# In[ ]:


max(abs(generacion_inicial - res.Sbus.real))  # error maximo de generacion

# Ahora buscamos los nudos de interes y eliminamos el resto.

# In[ ]:


# res.get_bus_df() # da error


# In[ ]:


buses_a_eliminar_nombre = []
for i in range(50, 65):
    buses_a_eliminar_nombre.append(f'BUS {i}')

# In[ ]:


buses_a_guardar = [bus for bus in grid.buses if bus.name.strip() not in buses_a_eliminar_nombre]
# buses_a_guardar = [bus for bus in grid.buses if bus.country.name == 'España' and (1 <= bus.Vnom) and (bus.Vnom >=220) or bus.is_slack]
len(buses_a_guardar)

# In[ ]:


grid2 = grid.copy()

# In[ ]:


# lista_codigos_eliminar = [
#     51063,
#     998688,
#     997001,
#     999360,
#     998238,
#     998685,
#     998687,
#     998164,
#     997000,
#     999291,
#     999359,
#     999358,
#     999290,
#     999296,
#     999295,
#     999289,
#     999256,
#     998326,
#     998595,
#     998237, 
#     999357,
# ]


# In[ ]:


buses_a_eliminar = []
for bus in grid2.buses:
    if bus not in buses_a_guardar:
        buses_a_eliminar.append(bus)
    # elif bus.code in lista_codigos_eliminar:
    #     buses_a_eliminar.append(bus)

for bus in buses_a_eliminar:
    grid2.delete_bus(bus, delete_associated=True)

len(grid2.buses)

# Ahora sacamos la PTDF reducida

# In[ ]:


res2 = vge.linear_power_flow(grid2)

# In[ ]:


PTDF_red = res2.mdl(vge.ResultTypes.PTDF).to_df()
PTDF_red.head(3)

# Ahora nos quedamos con los flujos de las branches que conectan nudos que nos interesan

# In[ ]:


branches_a_mantener = [line.name for line in grid.get_branches() if
                       (line.bus_from in buses_a_guardar) and (line.bus_to in buses_a_guardar)]

Fp_red = res.get_branch_df().loc[branches_a_mantener, 'Pf']
Fp_red.head(3)

# In[ ]:


from scipy.sparse.linalg import lsqr

# In[ ]:


generacion_reducida = np.linalg.lstsq(PTDF_red.to_numpy(), Fp_red.to_numpy(), rcond=None)[0]
generacion_reducida.shape

# In[ ]:


_generacion_reducida = lsqr(PTDF_red.to_numpy(), Fp_red.to_numpy())[0]

# In[ ]:


res_ = vge.linear_power_flow(grid2)

# In[ ]:


for bus, gen, sbus in zip(grid2.buses, generacion_reducida, res_.Sbus):

    if abs(sbus - gen) > 1e-5:
        print(bus.name, sbus, gen, gen - sbus)
        generator = grid2.add_generator(bus)
        generator.P = gen - sbus

# Flujo de cargas final para comprobar

# In[ ]:


res_final = vge.linear_power_flow(grid2)

error_flujos = res_final.get_branch_df()['Pf'].to_numpy() - Fp_red.to_numpy()

max(abs(error_flujos))

# In[ ]:


vge.save_file(grid2, 'caso_reducido.veragrid')
