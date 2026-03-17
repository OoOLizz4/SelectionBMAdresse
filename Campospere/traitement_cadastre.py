from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import *

from qgis.core import* # QgsVectorLayer,QgsRasterLayer, QgsProject, QgsField,QgsCoordinateTransform, QgsCoordinateReferenceSystem,QgsPointXY, QgsDistanceArea
from qgis.processing import *

class SelectionBmSelonAdresse(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('bm', 'BM', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('input_points', 'INPUT_POINTS', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('parcelles_cadastrales', 'PARCELLES_CADASTRALES', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Parcelles_selec', 'PARCELLES_SELEC', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue='./PARCELLES_SELEC'))
        self.addParameter(QgsProcessingParameterFeatureSink('Bm_adresse_selec', 'BM_Adresse_Selec', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        # Extraire par localisation
        alg_params = {
            'INPUT': parameters['parcelles_cadastrales'],
            'INTERSECT': parameters['input_points'],
            'PREDICATE': [1],  # contient
            'OUTPUT': parameters['Parcelles_selec']
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Parcelles_selec'] = outputs['ExtraireParLocalisation']['OUTPUT']

        # Extraire par localisation
        alg_params = {
            'INPUT': parameters['bm'],
            'INTERSECT': parameters['Parcelles_selec'],
            'PREDICATE': [6],  # est à l'intérieur
            'OUTPUT': parameters['Bm_adresse_selec']
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Bm_adresse_selec'] = outputs['ExtraireParLocalisation']['OUTPUT']

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        
        return results
    
    def name(self):
        return 'Selection BM selon adresse'

    def displayName(self):
        return 'Selection BM selon adresse'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return SelectionBmSelonAdresse()