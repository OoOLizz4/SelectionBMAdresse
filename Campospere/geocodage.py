# -*- coding: utf-8 -*-
# Geocodage des adresses via l'API BAN (Base Adresse Nationale)
# Transforme une couche avec des adresses texte en couche de points en Lambert 93

import urllib.request
import urllib.parse
import json

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
    QgsField, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsProject, QgsWkbTypes
)
from qgis.PyQt.QtCore import QVariant


def geocoder_couche(layer):
    """
    Prend une couche vecteur en entrée.
    Détecte automatiquement les colonnes disponibles.
    Retourne une couche de points en Lambert 93 (EPSG:2154).
    """

    # Transformation WGS84 → Lambert 93
    crs_wgs = QgsCoordinateReferenceSystem("EPSG:4326")
    crs_l93 = QgsCoordinateReferenceSystem("EPSG:2154")
    transform = QgsCoordinateTransform(crs_wgs, crs_l93, QgsProject.instance())

    # Si la couche est déjà des points → on la retourne directement
    if layer.geometryType() == QgsWkbTypes.PointGeometry:
        # Vérifier si elle est déjà en L93
        if layer.crs() == crs_l93:
            return layer
        # Sinon reprojeter
        else:
            return _reprojeter(layer, crs_l93)

    # Récupérer les noms de colonnes en majuscules pour comparaison
    champs = [f.name() for f in layer.fields()]
    champs_upper = [c.upper() for c in champs]

    # Détection automatique des colonnes adresse et code postal
    col_adresse = _trouver(champs, champs_upper, 'ADRESSE', 'ADDRESS', 'ADR')
    col_cp      = _trouver(champs, champs_upper, 'CODE_POSTAL', 'CODEPOSTAL', 'CP', 'POSTAL')
    col_commune = _trouver(champs, champs_upper, 'COMMUNE', 'VILLE', 'CITY')

    # Création de la couche de points en mémoire en L93
    couche_points = QgsVectorLayer("Point?crs=EPSG:2154", "sites_geocodes", "memory")
    couche_points.dataProvider().addAttributes([
        QgsField("adresse_geocodee", QVariant.String)
    ])
    couche_points.updateFields()
    couche_points.startEditing()

    nb_ok  = 0
    nb_err = 0

    for feat in layer.getFeatures():

        # Construction de la chaîne adresse à envoyer à l'API BAN
        adresse_str = ""
        if col_adresse:
            adresse_str += str(feat[col_adresse] or "").strip()
        if col_cp:
            adresse_str += " " + str(feat[col_cp] or "").strip()
        elif col_commune:
            adresse_str += " " + str(feat[col_commune] or "").strip()

        if not adresse_str.strip():
            nb_err += 1
            continue

        # Appel à l'API BAN pour obtenir les coordonnées
        lon, lat = _appel_ban(adresse_str)

        if lon is None:
            nb_err += 1
            continue

        # Conversion WGS84 → Lambert 93
        pt_l93 = transform.transform(QgsPointXY(lon, lat))

        # Ajout du point dans la couche
        new_feat = QgsFeature(couche_points.fields())
        new_feat["adresse_geocodee"] = adresse_str
        new_feat.setGeometry(QgsGeometry.fromPointXY(pt_l93))
        couche_points.addFeature(new_feat)
        nb_ok += 1

    couche_points.commitChanges()
    return couche_points


def _appel_ban(adresse_str):
    """
    Appelle l'API BAN avec une adresse texte.
    Retourne (longitude, latitude) en WGS84 ou (None, None) si non trouvé.
    """
    params = urllib.parse.urlencode({"q": adresse_str, "limit": 1})
    url = "https://api-adresse.data.gouv.fr/search/?{}".format(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        features = data.get("features", [])
        if not features:
            return None, None
        coords = features[0]["geometry"]["coordinates"]  # [lon, lat]
        return coords[0], coords[1]
    except Exception:
        return None, None


def _trouver(champs, champs_upper, *candidats):
    """
    Cherche un nom de colonne parmi une liste de candidats.
    Insensible à la casse.
    Retourne le nom original de la colonne ou None si non trouvé.
    """
    for candidat in candidats:
        for i, nom_upper in enumerate(champs_upper):
            if candidat in nom_upper:
                return champs[i]
    return None


def _reprojeter(layer, crs_cible):
    """
    Reprojette une couche de points vers un CRS cible.
    Retourne une nouvelle couche en mémoire.
    """
    src = layer.crs()
    transform = QgsCoordinateTransform(src, crs_cible, QgsProject.instance())

    couche_out = QgsVectorLayer("Point?crs=EPSG:2154", "points_reprojetes", "memory")
    couche_out.dataProvider().addAttributes(layer.fields().toList())
    couche_out.updateFields()
    couche_out.startEditing()

    for feat in layer.getFeatures():
        g = feat.geometry()
        g.transform(transform)
        new_feat = QgsFeature(couche_out.fields())
        new_feat.setAttributes(feat.attributes())
        new_feat.setGeometry(g)
        couche_out.addFeature(new_feat)

    couche_out.commitChanges()
    return couche_out