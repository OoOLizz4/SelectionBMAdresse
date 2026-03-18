from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import *

from qgis.core import* # QgsVectorLayer,QgsRasterLayer, QgsProject, QgsField,QgsCoordinateTransform, QgsCoordinateReferenceSystem,QgsPointXY, QgsDistanceArea

import processing
import shapefile

class SelectionBmSelonAdresse(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('bm', 'BM', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('input_points', 'INPUT_POINTS', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('parcelles_cadastrales', 'PARCELLES_CADASTRALES', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))        
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
            'OUTPUT': 'memory'
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        # Extraire par localisation
        alg_params = {
            'INPUT': parameters['bm'],
            'INTERSECT': outputs['ExtraireParLocalisation']['OUTPUT'],
            'PREDICATE': [6],  # est à l'intérieur
            'OUTPUT': 'C:/temp/parcelles.shp'        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Bm_adresse_selec'] = outputs['ExtraireParLocalisation']['OUTPUT']

        r = shapefile.Reader('C:/temp/parcelles.shp')

        w = shapefile.Writer("C:/temp/bmcada.shp")
        w.fields = r.fields[1:] # skip first deletion field

        # adding existing Shape objects
        for shaperec in r.iterShapeRecords():
            w.record(*shaperec.record)
            w.shape(shaperec.shape)
        
        w.close()

        layer = QgsVectorLayer("C:/temp/bmcada.shp", "bmcada", "ogr")
        QgsProject.instance().addMapLayer(layer)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        
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