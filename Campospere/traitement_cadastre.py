#Modules nécéssaires à l'affichage de l'interface
from qgis.PyQt.QtWidgets import *

#Modules nécéssaires à pour faire tourner le traitement vectoriel
from qgis.core import *
import processing

#Module pour naviguer plus facilement dans les fichiers
import os.path


class SelectionBmSelonAdresse(QgsProcessingAlgorithm):

    """
    Le traitement qui permet d'avoir la séléction des bâtiments modulaires selon une liste de point de coordonnées.
    Il est construit à partir du ModelBuilder de QGis.
    Il est lancé dans extract_bat_modulaire.py : Camposhere.traitement().
    Entrée :
        bm: Une couche .shp de polygone qui représente les bâtiments modulaires
        input_points: Une couche .shp qui représente les points de coordonnées des adresses
        parcelles_cadastrales: Une couche .shp qui représente les parcelles cadastrales du département qui nous intérèsse.
        nom_sortie: 

    Sortie : 
        Bm_adresse_selec: Une couche .shp qui représente les bâtiments modulaires séléctionnés en fonction des points d'adresse et des parcelles cadastrales.
    """

    def initAlgorithm(self, config=None):
        """Initialisation des paramètres"""
        self.addParameter(QgsProcessingParameterVectorLayer('bm', 'BM', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('input_points', 'INPUT_POINTS', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('parcelles_cadastrales', 'PARCELLES_CADASTRALES', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))        
        self.addParameter(QgsProcessingParameterString('nom_sortie', 'nom_sortie', multiLine=False, defaultValue='bmselec'))
        self.addParameter(QgsProcessingParameterFeatureSink('Bm_adresse_selec', 'BM_Adresse_Selec', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))


    def processAlgorithm(self, parameters, context, model_feedback):
        """Traitement"""
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        
        #**************************# ← AJOUTER : reprojection des points en L93 ******************************
        from qgis.core import QgsCoordinateReferenceSystem
        couche_points = self.parameterAsVectorLayer(parameters, 'input_points', context)
        crs_l93 = QgsCoordinateReferenceSystem("EPSG:2154")

        if couche_points.crs() != crs_l93:
            outputs['points_l93'] = processing.run(
                'native:reprojectlayer',
                {'INPUT': couche_points, 'TARGET_CRS': crs_l93, 'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT},
                context=context, feedback=feedback, is_child_algorithm=True
            )
            points_pour_traitement = outputs['points_l93']['OUTPUT']
        else:
            points_pour_traitement = parameters['input_points']


        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        
         # Réparer les géométries : je répare la géométrie des parcelles cadastrales pour avoir un meilleur résultat lors du traitement
        alg_params = {
            'INPUT': parameters['parcelles_cadastrales'],
            'METHOD': 1,  # Structure
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RparerLesGomtries'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}


        # Extraire par localisation : on choisit les parcelles dans lesquelles il y a des points
        alg_params = {
            'INPUT': outputs['RparerLesGomtries']['OUTPUT'],
            'INTERSECT': parameters['input_points'],
            'PREDICATE': [0],  # intersecte
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        
        # Extraire par localisation : on choisit les bâtiments modulaires qui sont dans les parcelles choisies plus tôt
        alg_params = {
            'INPUT': parameters['bm'],
            'INTERSECT': outputs['ExtraireParLocalisation']['OUTPUT'],
            'PREDICATE': [6],  # est à l'intérieur
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT      
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # Joindre les attributs par localisation : on ajoute le nom de la parcelle cadastrale à la table d'attribut
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'INPUT': outputs['ExtraireParLocalisation']['OUTPUT'],
            'JOIN': outputs['RparerLesGomtries']['OUTPUT'],
            'JOIN_FIELDS': ['id'],
            'METHOD': 0,  # Cr�er une entit� distincte pour chaque entit� correspondante (un � plusieurs)
            'PREDICATE': [0],  # intersecte
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoindreLesAttributsParLocalisation'] = processing.run('native:joinattributesbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Renommer le champ : changement du nom pour un nom plus parlant
        alg_params = {
            'FIELD': 'id_2',
            'INPUT': outputs['JoindreLesAttributsParLocalisation']['OUTPUT'],
            'NEW_NAME': 'id_parcelle',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RenommerLeChamp'] = processing.run('native:renametablefield', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
        
        cheminSortieShp = "C:/temp/"+parameters['nom_sortie']+".shp"

        # Supprimer champ(s) : suppression des champs qui sont inutiles
        alg_params = {
            'COLUMN': ['Section_ca','numero_par','Section__1','numero_p_1'],
            'INPUT': outputs['RenommerLeChamp']['OUTPUT'],
            'OUTPUT': cheminSortieShp
        }
        outputs['SupprimerChamps'] = processing.run('native:deletecolumn', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Testtablepropre'] = outputs['SupprimerChamps']['OUTPUT']

        # Transformation du résultat en couche QGis et affichage de celle-ci
        coucheSortie = QgsVectorLayer(cheminSortieShp, parameters['nom_sortie'], "ogr")
        QgsProject.instance().addMapLayer(coucheSortie)

        # Chargement du style customisé
        plugin_dir = os.path.dirname(__file__)

        style_path = os.path.join(plugin_dir, 'styleCouches', 'style_resultat.qml')

        coucheSortie.loadNamedStyle(style_path)
        coucheSortie.triggerRepaint()

        return results
    
    def name(self):
        return 'selectionBMCadastre'

    def displayName(self):
        return 'selectionBMCadastre'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return SelectionBmSelonAdresse()
    
class ProviderTraitement(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(SelectionBmSelonAdresse())

    def id(self):
        return "providerT"

    def name(self):
        return "providerT"