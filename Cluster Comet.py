import math 
from PyQt5.QtCore import QVariant 
from qgis.core import QgsField 
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QComboBox 

# Función que solicita al usuario la columna que desea usar 
def solicitar_columna(layer): 
    # Obtener los nombres de todas las columnas 
    field_names = [field.name() for field in layer.fields()] 
    # Crear un cuadro de diálogo para seleccionar la columna 
    columna, ok = QInputDialog.getItem(None, "Seleccionar Columna", "Selecciona la columna que delimitará los subgrupos:", field_names, 0, False) 
    if not ok: 
        return None # Si el usuario cancela 
    return columna 

# Función que solicita al usuario el valor de la columna seleccionada (como sector) 
def solicitar_valor_columna(layer, columna): 
    # Obtener los valores únicos de la columna seleccionada 
    values = set(feature[columna] for feature in layer.getFeatures()) 
    # Crear un cuadro de diálogo para seleccionar el valor 
    value, ok = QInputDialog.getItem(None, f"Agrupar de acuerdo con {columna}", f"Selecciona el valor para agrupar según {columna}:", list(values), 0, False) 
    if not ok: 
        return None # Si el usuario cancela 
    return value 

# Nueva función que solicita al usuario la columna de población a usar
def solicitar_columna_poblacion(layer):
    # Obtener los nombres de todas las columnas
    field_names = [field.name() for field in layer.fields()]
    # Filtrar solo las columnas numéricas
    numeric_fields = [name for name in field_names if name != 'SUBGRUPOS' and isinstance(layer.dataProvider().fieldNameIndex(name), int)]  
    # Crear un cuadro de diálogo para seleccionar la columna
    columna_poblacion, ok = QInputDialog.getItem(None, "Seleccionar Columna Numérica", "Selecciona la columna para basar la creación de subgrupos:", numeric_fields, 0, False)
    if not ok:
        return None  # Si el usuario cancela
    return columna_poblacion

# Función que solicita al usuario la cantidad de subgrupos y la orientación 
def solicitar_entrada(valor): 
    # Solicitar número de subgrupos 
    num_subgroups, ok = QInputDialog.getInt(None, "Número de Subgrupos", f"¿Cuántos subgrupos quieres según {valor}?", 1, 1, 100) 
    if not ok: 
        return None, None # Si el usuario cancela 
    # Solicitar orientación 
    orientation, ok = QInputDialog.getItem(None, "Seleccionar Orientación", f"¿Qué orientación quieres para {valor}?", ["norte a sur", "sur a norte"], 0, False) 
    if not ok: 
        return None, None # Si el usuario cancela 
    return num_subgroups, orientation 

# Función para filtrar las entidades según el valor de la columna seleccionada 
def obtener_features_por_columna(layer, columna, valor): 
    return [feature for feature in layer.getFeatures() if feature[columna] == valor] 

# Función para ordenar las entidades por su latitud según la orientación 
def ordenar_features(features, orientation): 
    return sorted(features, key=lambda feature: feature.geometry().centroid().asPoint().y(), reverse=(orientation == 'norte a sur')) 

# Función para verificar si dos entidades son vecinas (intersectan) 
def is_neighbor(feature1, feature2): 
    return feature1.geometry().intersects(feature2.geometry()) 

# Función para formar subgrupos con el límite actual 
def form_subgroups(features, limit, current_group_base, layer, columna_poblacion): 
    visited = set() 
    subgroup_count = 1 
    for feature in features: 
        if feature.id() not in visited: 
            current_population = 0 
            group_features = [feature] 
            current_population += feature[columna_poblacion]  # Cambiar aquí
            visited.add(feature.id()) 
            while group_features: 
                current_feature = group_features.pop() 
                # Asegurarse de que la capa está en modo edición 
                if not layer.isEditable(): 
                    layer.startEditing() 
                # Asegurar que el campo 'SUBGRUPOS' exista 
                if 'SUBGRUPOS' not in [field.name() for field in layer.fields()]: 
                    layer.dataProvider().addAttributes([QgsField('SUBGRUPOS', QVariant.String, len=254)]) 
                    layer.updateFields() 
                current_feature['SUBGRUPOS'] = f"{current_group_base} {subgroup_count}" 
                layer.updateFeature(current_feature) 
                for neighbor in features: 
                    if neighbor.id() not in visited and is_neighbor(current_feature, neighbor): 
                        if current_population + neighbor[columna_poblacion] <= limit:  # Cambiar aquí
                            current_population += neighbor[columna_poblacion]  # Cambiar aquí
                            visited.add(neighbor.id()) 
                            group_features.append(neighbor) 
            subgroup_count += 1 # Incrementar subgrupo al finalizar 
    return subgroup_count - 1 # Número total de subgrupos formados 

# Función principal para ejecutar el proceso 
def asignar_subgrupos(layer): 
    # Primero, solicitar la columna 
    columna = solicitar_columna(layer) 
    if not columna: 
        QMessageBox.warning(None, "Error", "El proceso fue cancelado.") 
        return 
    # Luego, solicitar el valor de la columna (como sector) 
    valor = solicitar_valor_columna(layer, columna) 
    if not valor: 
        QMessageBox.warning(None, "Error", "El proceso fue cancelado.") 
        return 
    # Solicitar la columna de población
    columna_poblacion = solicitar_columna_poblacion(layer)
    if not columna_poblacion:
        QMessageBox.warning(None, "Error", "El proceso fue cancelado.") 
        return
    # Ahora, pedir el número de subgrupos y la orientación 
    num_subgroups, orientation = solicitar_entrada(valor) 
    if num_subgroups is None: 
        QMessageBox.warning(None, "Error", "El proceso fue cancelado.") 
        return 
    current_group_base = f'{valor}, subgrupo' 
    # Filtrar las características del sector seleccionado 
    features = obtener_features_por_columna(layer, columna, valor) 
    # Calcular la población total para el sector 
    total_population = sum(feature[columna_poblacion] for feature in features) 
    # Calcular la población ideal por subgrupo 
    ideal_population = total_population / num_subgroups 
    current_limit = ideal_population # Límite dinámico inicial 
    # Ordenar las entidades según la orientación 
    features_sorted = ordenar_features(features, orientation) 
    # Ajustar dinámicamente el límite de población 
    while True: 
        total_subgroups = form_subgroups(features_sorted, current_limit, current_group_base, layer, columna_poblacion) 
        if total_subgroups == num_subgroups: 
            break 
        current_limit = math.ceil(current_limit + 10) # Incrementar el límite y redondear 
    layer.commitChanges() 
    
    # Mensaje al finalizar el proceso 
    QMessageBox.information(None, "Código Cluster Comet: Proceso completado", 
                            f"Columna delimitante: {columna}\n" 
                            f"Opción delimitante: {valor}\n" 
                            f"Columna numérica seleccionada: {columna_poblacion}\n"
                            f"Subgrupos creados: {num_subgroups}\n" 
                            f"Límite final de población utilizado: {math.ceil(current_limit)}\n" 
                            f"Orientación seleccionada: {orientation}\n" 
                            f"\n" 
                            f"Consulta el resultado en la columna SUBGRUPOS\n"
                            f"Código Cluster Comet creado por MFRB \n")
                            

# Llamada a la función principal 
asignar_subgrupos(iface.activeLayer()) 
