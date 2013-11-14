# -*- coding: utf-8 -*-
from email.header import Header

from Testing import ZopeTestCase as ztc
from zope.event import notify
from zope.interface import alsoProvides
from zope.lifecycleevent import ObjectModifiedEvent
from plone.rfc822 import constructMessageFromSchemata
from plone.rfc822 import initializeObjectFromSchemata
from plone.uuid.interfaces import IUUID
from zope.configuration import xmlconfig
from Products.CMFCore.utils import getToolByName
from plone.app.multilingual.dx.interfaces import ILanguageIndependentField

from plone.app.multilingual.interfaces import ITranslationManager
from plone.app.robotframework.remote import RemoteLibrary
from plone.app.robotframework import RemoteLibraryLayer
from plone.app.robotframework import AutoLogin
from plone.app.robotframework import Content
from plone.testing import z2
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import TEST_USER_ID
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import applyProfile
from plone.app.testing import ploneSite
from plone.app.testing import setRoles
from plone.app.multilingual.browser.setup import SetupMultilingualSite
from plone.dexterity.utils import createContentInContainer
from plone.dexterity.utils import iterSchemata
from plone.app.multilingual.interfaces import ILanguage
import plone.app.multilingual
import plone.app.dexterity


class Sessions(z2.Layer):

    defaultBases = (PLONE_FIXTURE,)

    def setUp(self):
        with z2.zopeApp() as app:
            ztc.utils.setupCoreSessions(app)

    def testTearDown(self):
        with z2.zopeApp() as app:
            # Clean up sessions after each test
            app.session_data_manager._p_jar.sync()
            app.session_data_manager._getSessionDataContainer()._reset()

            # Commit transaction
            from transaction import commit
            commit()

SESSIONS_FIXTURE = Sessions()


class PloneAppMultilingualLayer(PloneSandboxLayer):

    defaultBases = (SESSIONS_FIXTURE, PLONE_APP_CONTENTTYPES_FIXTURE)

    def setUpZope(self, app, configurationContext):
        # load ZCML
        xmlconfig.file('configure.zcml', plone.app.multilingual,
                       context=configurationContext)

        xmlconfig.file('overrides.zcml', plone.app.multilingual,
                       context=configurationContext)

        # Enable languageindependent-field on IRelatedItems-behavior
        from plone.app.relationfield.behavior import IRelatedItems
        alsoProvides(IRelatedItems['relatedItems'], ILanguageIndependentField)

    def setUpPloneSite(self, portal):
        # install into the Plone site
        applyProfile(portal, 'plone.app.multilingual:default')
        setRoles(portal, TEST_USER_ID, ['Manager'])

PLONE_APP_MULTILINGUAL_FIXTURE = PloneAppMultilingualLayer()


class TwoLanguagesLayer(z2.Layer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE, )

    def setUp(self):
        def translate(obj, target_language='en'):
            manager = ITranslationManager(obj)
            manager.add_translation(target_language)
            return manager.get_translation(target_language)

        with ploneSite() as portal:
            # Define available languages
            language_tool = getToolByName(portal, 'portal_languages')
            language_tool.addSupportedLanguage('ca')
            language_tool.addSupportedLanguage('es')

            # Setup language root folders
            setupTool = SetupMultilingualSite()
            setupTool.setupSite(portal)

            # Create sample content
            document = createContentInContainer(
                portal['en'], 'Document',
                id='test-document', title=u"EN test document")
            ILanguage(document).set_language('en')

            # Create sample translation
            translation = translate(document, 'ca')
            translation.title = u"CA test document"
            ILanguage(translation).set_language('ca')

TWO_LANGUAGES_FIXTURE = TwoLanguagesLayer()


class MultiLingual(RemoteLibrary):

    def create_translation(self, *args, **kwargs):
        """Create translation for an object with uid in the given
        target_language and return its UID

        Usage::

            Create translation  /plone/en/foo  ca  title=Translated
        """
        # XXX: **kwargs do not yet with Robot Framework remote libraries
        # Parse arguments:
        uid_or_path = args[0]
        target_language = args[1]
        kwargs = dict([arg.split('=', 1) for arg in args[2:]])

        # Look up translatable content
        pc = getToolByName(self, "portal_catalog")
        uid_results = pc.unrestrictedSearchResults(UID=uid_or_path)
        path_results = pc.unrestrictedSearchResults(
            path={'query': uid_or_path.rstrip('/'), 'depth': 0})
        obj = (uid_results or path_results)[0]._unrestrictedGetObject()

        # Translate
        manager = ITranslationManager(obj)
        manager.add_translation(target_language)
        translation = manager.get_translation(target_language)

        # Update fields
        data = constructMessageFromSchemata(obj, iterSchemata(obj))
        for key, value in kwargs.items():
            del data[key]
            data[key] = Header(value, 'utf-8')
        del data['language']
        initializeObjectFromSchemata(translation, iterSchemata(obj), data)
        notify(ObjectModifiedEvent(translation))

        # Return uid for the translation
        return IUUID(translation)


REMOTE_LIBRARY_BUNDLE_FIXTURE = RemoteLibraryLayer(
    bases=(PLONE_FIXTURE,),
    libraries=(AutoLogin, Content, MultiLingual),
    name="RemoteLibraryBundle:RobotRemote"
)

PLONE_APP_MULTILINGUAL_INTEGRATION_TESTING = IntegrationTesting(
    bases=(PLONE_APP_MULTILINGUAL_FIXTURE,),
    name="plone.app.multilingual:Integration")
PLONE_APP_MULTILINGUAL_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(PLONE_APP_MULTILINGUAL_FIXTURE,),
    name="plone.app.multilingual:Functional")
PLONE_APP_MULTILINGUAL_ROBOT_TESTING = FunctionalTesting(
    bases=(PLONE_APP_MULTILINGUAL_FIXTURE,
           TWO_LANGUAGES_FIXTURE,
           REMOTE_LIBRARY_BUNDLE_FIXTURE,
           z2.ZSERVER_FIXTURE),
    name="plone.app.multilingual:Robot")
