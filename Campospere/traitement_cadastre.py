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

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Extraire par localisation : on choisit les parcelles dans lesquelles il y a des points
        alg_params = {
            'INPUT': parameters['parcelles_cadastrales'],
            'INTERSECT': parameters['input_points'],
            'PREDICATE': [0],  # intersecte
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        cheminSortie = "C:/temp/"+parameters['nom_sortie']+".shp"

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        
        # Extraire par localisation : on choisit les bâtiments modulaires qui sont dans les parcelles choisies plus tôt
        alg_params = {
            'INPUT': parameters['bm'],
            'INTERSECT': outputs['ExtraireParLocalisation']['OUTPUT'],
            'PREDICATE': [6],  # est à l'intérieur
            'OUTPUT': cheminSortie      }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Bm_adresse_selec'] = outputs['ExtraireParLocalisation']['OUTPUT']

        # Transformation du résultat en couche QGis et affichage de celle-ci
        coucheSortie = QgsVectorLayer(cheminSortie, parameters['nom_sortie'], "ogr")
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