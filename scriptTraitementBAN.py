"""
Model exported as python.
Name : Selection BM selon adresse
Group : 
With QGIS : 34007
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterMatrix
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class SelectionBmSelonAdresse(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('adresses', 'ADRESSES', types=[QgsProcessing.TypeVector], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('donnees_ban', 'DONNEES_BAN', defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Adresse_propre', 'ADRESSE_PROPRE', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Donnees_ban_propres', 'DONNEES_BAN_PROPRES', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Points_avec_coord', 'POINTS_AVEC_COORD', optional=True, type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('parcelles_cadastrales', 'PARCELLES_CADASTRALES', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Parcelles_selec', 'PARCELLES_SELEC', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue='./PARCELLES_SELEC'))
        self.addParameter(QgsProcessingParameterVectorLayer('bm', 'BM', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Bm_adresse_selec', 'BM_Adresse_Selec', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(5, model_feedback)
        results = {}
        outputs = {}

        # Calculatrice de Champ : création champ adresse propre pour DONNEES_BAN
        alg_params = {
            'FIELD_LENGTH': 100,
            'FIELD_NAME': 'ADRESSE_CONCAT',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # Texte (cha�ne de caract�res)
            'FORMULA': "lower('numero'+'rep'+'nom_voie'+' insee_com') ",
            'INPUT': parameters['donnees_ban'],
            'OUTPUT': parameters['Donnees_ban_propres']
        }
        outputs['CalculatriceDeChamp'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Donnees_ban_propres'] = outputs['CalculatriceDeChamp']['OUTPUT']

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Calculatrice de champ : création champ adresse propre pour ADRESSES
        alg_params = {
            'FIELD_LENGTH': 100,
            'FIELD_NAME': 'ADRESSE_CONCAT',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # Texte (cha�ne de caract�res)
            'FORMULA': "lower('ADRESSE_POSTALE'+'CODE_POSTAL')",
            'INPUT': parameters['adresses'],
            'OUTPUT': parameters['Adresse_propre']
        }
        outputs['CalculatriceDeChamp'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Adresse_propre'] = outputs['CalculatriceDeChamp']['OUTPUT']

        # Joindre les attributs par valeur de champ : Je garde les coord des adresses dans la liste d'adresse
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'FIELD': 'ADRESSE_CONCAT',
            'FIELDS_TO_COPY': [''],
            'FIELD_2': 'ADRESSE_CONCAT',
            'INPUT': parameters['Adresse_propre'],
            'INPUT_2': parameters['Donnees_ban_propres'],
            'METHOD': 1,  # Prendre uniquement les attributs de la premi�re entit� correspondante (un � un)
            'PREFIX': '',
            'OUTPUT': parameters['Points_avec_coord']
        }
        outputs['JoindreLesAttributsParValeurDeChamp'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Points_avec_coord'] = outputs['JoindreLesAttributsParValeurDeChamp']['OUTPUT']

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Extraire par localisation
        alg_params = {
            'INPUT': parameters['parcelles_cadastrales'],
            'INTERSECT': parameters['Points_avec_coord'],
            'PREDICATE': [1],  # contient
            'OUTPUT': parameters['Parcelles_selec']
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Parcelles_selec'] = outputs['ExtraireParLocalisation']['OUTPUT']

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}
        
        # Extraire par localisation
        alg_params = {
            'INPUT': parameters['bm'],
            'INTERSECT': parameters['parcelles_selec'],
            'PREDICATE': [6],  # est à l'intérieur
            'OUTPUT': parameters['Bm_adresse_selec']
        }
        outputs['ExtraireParLocalisation'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Bm_adresse_selec'] = outputs['ExtraireParLocalisation']['OUTPUT']

        feedback.setCurrentStep(3)
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
