# -*- coding: utf-8 -*-

"""
geocodage.py
Script de géocodage pour le plugin Camposphere.
Basé sur le script original de géocodage Nominatim du pluging MMQGIS,
On a mis en commentaire tout ce qu'on ajouter ou adapter
"""

import csv
import os
import urllib.request   # ← AJOUT : remplace 'requests' (pas besoin d'installation externe)
import urllib.parse     # ← AJOUT : pour construire l'URL de l'API BAN
import json             # ← AJOUT : pour lire la réponse de l'API BAN

from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature,
    QgsGeometry, QgsPointXY, QgsProject,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QMessageBox  # ← AJOUT : messages d'erreur dans QGIS

# ← AJOUT : support des fichiers Excel .xlsx / .xls
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# GÉOCODAGE BAN
# ← AJOUT complet : remplace geocode() Nominatim du script original
# Différences vs Nominatim :
#   - URL BAN au lieu de nominatim.openstreetmap.org

def geocoder_ban(adresse_str):
    if not adresse_str.strip():
        return None, None
    url = "https://api-adresse.data.gouv.fr/search/?" + \
          urllib.parse.urlencode({'q': adresse_str, 'limit': 1})
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
            feats = data.get('features', [])
            # ← AJOUT : vérification du score de confiance
            if feats and feats[0]['properties'].get('score', 0) > 0.4:
                coords = feats[0]['geometry']['coordinates']
                return float(coords[0]), float(coords[1])
    except Exception as e:
        print(f"Erreur BAN : {adresse_str} → {e}")
    return None, None


# LECTURE DU FICHIER
# ← AJOUT complet : le script original lisait un seul CSV avec chemin fixe
# Ici : CSV + XLSX, encodage auto, séparateur auto, titres fusionnés gérés

def lire_fichier(chemin):
    ext = os.path.splitext(chemin)[1].lower()

    if ext == '.csv':
        # ← AJOUT : détection automatique de l'encodage
        encodage = 'utf-8-sig'
        for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                with open(chemin, 'r', encoding=enc) as f:
                    f.read(1024)
                encodage = enc
                break
            except UnicodeDecodeError:
                continue

        # ← AJOUT : détection automatique du séparateur ; ou ,
        with open(chemin, 'r', encoding=encodage) as f:
            debut = f.read(2048)
        sep = ';' if debut.count(';') > debut.count(',') else ','

        lignes = []
        with open(chemin, 'r', encoding=encodage) as f:
            reader = csv.DictReader(f, delimiter=sep)
            colonnes = list(reader.fieldnames or [])
            for row in reader:
                lignes.append(dict(row))
        return colonnes, lignes

    elif ext in ('.xlsx', '.xls'):
        # ← AJOUT complet : lecture Excel non présente dans le script original
        if not HAS_OPENPYXL:
            raise ImportError("Installez openpyxl : pip install openpyxl")
        wb = openpyxl.load_workbook(chemin, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        # ← AJOUT : ignore les titres fusionnés en ligne 0
        # (ex: "Collèges Publics - Yvelines (78)" dans colleges.xlsx)
        entete_idx = 0
        for i, row in enumerate(rows):
            if sum(1 for v in row if v is not None and str(v).strip()) >= 3:
                entete_idx = i
                break

        colonnes = [str(c).strip() if c else f"col_{i}"
                    for i, c in enumerate(rows[entete_idx])]
        lignes = []
        for row in rows[entete_idx + 1:]:
            if any(v is not None and str(v).strip() for v in row):
                lignes.append({
                    colonnes[i]: str(row[i]).strip() if i < len(row) and row[i] is not None else ''
                    for i in range(len(colonnes))
                })
        return colonnes, lignes

    else:
        raise ValueError(f"Format non supporté : {ext}")

# DÉTECTION DU FORMAT
# ← AJOUT complet : le script original avait une colonne 'adresse' fixe
# Ici : détection automatique parmi 4 modes selon les noms de colonnes


def detecter_format(colonnes, lignes):
    col_map = {c.lower().strip(): c for c in colonnes}
    noms = set(col_map.keys())

    # ← AJOUT : Mode 1 — colonnes lon/lat séparées explicites
    NOMS_LON = {'lon', 'longitude', 'long', 'lng', 'x_wgs84'}
    NOMS_LAT = {'lat', 'latitude', 'y_wgs84'}
    col_lon = next((col_map[n] for n in NOMS_LON if n in noms), None)
    col_lat = next((col_map[n] for n in NOMS_LAT if n in noms), None)
    if col_lon and col_lat:
        return 'lon_lat', col_lon, col_lat

    # ← AJOUT : Mode 2 — colonnes x/y Lambert 93 (ex: gares IDF)
    NOMS_X = {'x', 'x_l93', 'x_coord', 'coord_x'}
    NOMS_Y = {'y', 'y_l93', 'y_coord', 'coord_y'}
    col_x = next((col_map[n] for n in NOMS_X if n in noms), None)
    col_y = next((col_map[n] for n in NOMS_Y if n in noms), None)
    if col_x and col_y:
        # ← AJOUT : détecte si Lambert93 (valeurs > 1000) ou WGS84
        try:
            val_test = float(str(lignes[0][col_x]).replace(',', '.'))
            epsg = 2154 if val_test > 1000 else 4326
        except Exception:
            epsg = 4326
        return 'xy', col_x, (col_y, epsg)

    # ← AJOUT : Mode 3 — colonne combinée "lon,lat" ou "lat,lon"
    # (ex: colonne 'centroid' dans DPT78.csv qu'on a à notre disposition, 'GEO' dans lycees.csv)
    NOMS_COMBO = {'centroid', 'geo point', 'geo', 'geometry',
                  'coordinates', 'geom', 'localisation', 'position'}
    col_combo = next((col_map[n] for n in NOMS_COMBO if n in noms), None)
    if col_combo:
        return 'combo', col_combo, None

    # Mode 4 — colonnes texte → géocodage BAN
    # (présent dans le script original mais avec colonne fixe 'adresse')
    # ← AJOUT : détection automatique des colonnes adresse, CP, ville
    NOMS_ADR = {'adresse', 'adresse entière', 'adresse entiere',
                'address', 'rue', 'voie', 'libelle_adr'}
    NOMS_CP  = {'code postal', 'cp', 'codepostal', 'postal_code'}
    NOMS_VIL = {'commune', 'ville', 'city', 'municipality'}
    col_adr = next((col_map[n] for n in NOMS_ADR if n in noms), None)
    col_cp  = next((col_map[n] for n in NOMS_CP  if n in noms), None)
    col_vil = next((col_map[n] for n in NOMS_VIL if n in noms), None)
    if col_adr or (col_cp and col_vil):
        return 'adresse', (col_adr, col_cp, col_vil), None

    return 'inconnu', None, None


# ← AJOUT complet : compose une adresse propre depuis plusieurs colonnes
# (le script original lisait une seule colonne 'adresse' déjà prête)
def composer_adresse(ligne, col_adr, col_cp, col_vil):
    col_map = {c.lower().strip(): c for c in ligne.keys()}

    # ← AJOUT : récupère le numéro de voie si présent
    num = ''
    for n in ('no° voie', 'no voie', 'numero', 'num_voie'):
        if n in col_map:
            num = ligne[col_map[n]].strip()
            break

    adr = ligne.get(col_adr, '').strip() if col_adr else ''
    cp  = ligne.get(col_cp,  '').strip() if col_cp  else ''
    vil = ligne.get(col_vil, '').strip() if col_vil else ''

    # ← AJOUT : nettoie "78 - ACHERES" → "ACHERES"
    if ' - ' in vil:
        vil = vil.split(' - ', 1)[1].strip()

    adresse_str = f"{num} {adr}".strip()
    # ← AJOUT : ajoute CP si absent de l'adresse
    if cp and cp not in adresse_str:
        adresse_str += f" {cp}"
    if vil:
        adresse_str += f" {vil}"

    return adresse_str.strip()


# ← AJOUT complet : parse une colonne combinée "lon,lat" ou "lat,lon"
# Détecte l'ordre automatiquement selon les valeurs
def parser_combo(val):
    try:
        val = str(val).strip().strip('"')
        a, b = [float(p.strip()) for p in val.split(',')[:2]]
        # ← AJOUT : latitude France entre 42 et 51 → si a dans cet intervalle = lat,lon
        if 42 <= a <= 51:
            return b, a  # inverse pour retourner toujours (lon, lat)
        return a, b
    except Exception:
        return None, None


# Emprise France métropolitaine — pour filtrer les points hors-France
FRANCE_LON_MIN, FRANCE_LON_MAX = -5.5, 10.0
FRANCE_LAT_MIN, FRANCE_LAT_MAX = 41.0, 52.0

def _valider_point_france(lon, lat):
    """Retourne False si le point est hors France (océan, Afrique...)."""
    return (FRANCE_LON_MIN <= lon <= FRANCE_LON_MAX and
            FRANCE_LAT_MIN <= lat <= FRANCE_LAT_MAX)

def _reprojeter_vers_l93(couche_wgs84):
    """Reprojette la couche WGS84 → Lambert 93 pour que l'intersection fonctionne."""
    crs_wgs = QgsCoordinateReferenceSystem("EPSG:4326")
    crs_l93 = QgsCoordinateReferenceSystem("EPSG:2154")
    transform = QgsCoordinateTransform(crs_wgs, crs_l93, QgsProject.instance())
    out = QgsVectorLayer("Point?crs=EPSG:2154", couche_wgs84.name() + "_L93", "memory")
    out.dataProvider().addAttributes(couche_wgs84.fields().toList())
    out.updateFields()
    out.startEditing()
    for feat in couche_wgs84.getFeatures():
        g = feat.geometry()
        g.transform(transform)
        nf = QgsFeature(out.fields())
        nf.setAttributes(feat.attributes())
        nf.setGeometry(g)
        out.addFeature(nf)
    out.commitChanges()
    return out

# FONCTION PRINCIPALE
# ← AJOUT : remplace le bloc principal du script original
# Le script original : chemin fixe, une seule colonne, un seul format
# Ici : chemin passé en paramètre, détection auto, 4 modes


def importer_et_geocoder(chemin_fichier):
    """Appelée depuis l'interface : layer = importer_et_geocoder(chemin)"""

    if not os.path.exists(chemin_fichier):
        QMessageBox.warning(None, "Fichier introuvable", chemin_fichier)
        return None

    try:
        colonnes, lignes = lire_fichier(chemin_fichier)
    except Exception as e:
        QMessageBox.critical(None, "Erreur lecture", str(e))
        return None

    if not lignes:
        QMessageBox.warning(None, "Fichier vide", "Aucune donnée trouvée.")
        return None

    nom = os.path.splitext(os.path.basename(chemin_fichier))[0]
    mode, param1, param2 = detecter_format(colonnes, lignes)  # ← AJOUT
    paires = []

    if mode == 'lon_lat':           # ← AJOUT
        for l in lignes:
            try:
                paires.append((float(l[param1]), float(l[param2])))
            except Exception:
                paires.append((None, None))
        epsg, methode = 4326, f"colonnes '{param1}'/'{param2}'"

    elif mode == 'xy':              # ← AJOUT
        col_y, epsg = param2
        for l in lignes:
            try:
                paires.append((float(str(l[param1]).replace(',', '.')),
                               float(str(l[col_y]).replace(',', '.'))))
            except Exception:
                paires.append((None, None))
        methode = f"colonnes '{param1}'/'{col_y}' EPSG:{epsg}"

    elif mode == 'combo':           # ← AJOUT
        paires  = [parser_combo(l[param1]) for l in lignes]
        epsg    = 4326
        methode = f"colonne '{param1}'"

    elif mode == 'adresse':         # présent dans l'original, généralisé ici
        col_adr, col_cp, col_vil = param1
        for l in lignes:
            adresse_str = composer_adresse(l, col_adr, col_cp, col_vil)  # ← AJOUT
            print(f"Géocodage BAN : {adresse_str}")
            paires.append(geocoder_ban(adresse_str))
        epsg    = 4326
        methode = "géocodage API BAN"

    else:
        # ← AJOUT : message d'erreur explicite avec les colonnes trouvées
        QMessageBox.warning(
            None, "Format non reconnu",
            f"Colonnes trouvées : {', '.join(colonnes)}\n\n"
            "Noms reconnus pour coordonnées :\n"
            "  x, y, lon, lat, longitude, latitude,\n"
            "  centroid, geo, geo point...\n\n"
            "Noms reconnus pour adresse :\n"
            "  adresse, rue, commune, code postal..."
        )
        return None

    # ─── Création de la couche QGIS ───
    # Structure identique au script original
    vl = QgsVectorLayer(f'Point?crs=EPSG:{epsg}', nom, 'memory')
    pr = vl.dataProvider()
    # ← AJOUT : tous les champs du fichier sont conservés (pas seulement adresse/lat/lon)
    pr.addAttributes([QgsField(col[:10], QVariant.String) for col in colonnes])
    vl.updateFields()

    features, nb_erreurs, nb_hors_france = [], 0, 0
    for i, ligne in enumerate(lignes):
        lon, lat = paires[i]
        if lon is None or lat is None:
            nb_erreurs += 1
            continue
          # ← AJOUTER : filtre les points hors France
        if epsg == 4326 and not _valider_point_france(lon, lat):
            nb_hors_france += 1
            continue
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
        feat.setAttributes([str(ligne.get(col, '')) for col in colonnes])
        features.append(feat)

    pr.addFeatures(features)
    vl.updateExtents()
    # ← AJOUTER : reprojection systématique en L93 (sinon l'intersection cadastre rate)
    if epsg == 4326 and vl.featureCount() > 0:
        vl = _reprojeter_vers_l93(vl)
    QgsProject.instance().addMapLayer(vl)

    # ← AJOUT : message de confirmation avec résumé
    QMessageBox.information(
        None, " Import réussi",
        f"Couche '{nom}' créée.\n"
        f"Points : {vl.featureCount()}\n"
        f"Méthode : {methode}\n"
        f"Lignes ignorées : {nb_erreurs}"
    )
    return vl
