# :coding: utf-8
# :copyright: Copyright (c) 2015 ftrack

import os
import tempfile
import logging

import nuke
import hiero
from clique import Collection

import ftrack_connect_nuke_studio.processor

FILE_PATH = os.path.dirname(os.path.abspath(__file__))


def create_script(node, start_frame, end_frame):
    print("aroma_debug: create_script")

    (file, path) = tempfile.mkstemp(prefix="hiero_")

    # create a script writer
    nukeScriptWriter = hiero.core.nuke.ScriptWriter()

    nukeScriptWriter.addNode(node)

    # create a write node
    writeNodeOutput = 'C:\tmp\shot.mov'
    writeNode = nuke.WriteNode(writeNodeOutput)
    writeNode.setKnob("first", start_frame)
    writeNode.setKnob("last", end_frame)

    # add the write node to the script
    nukeScriptWriter.addNode(writeNode)

    # write the script to disk
    scriptPath = 'C:\tmp\script.nk'
    nukeScriptWriter.writeToDisk(scriptPath)

def create_component():
    ''' Create component callback for nuke write nodes.

    This callback relies on two custom knobs:
        * asset_version_id , which refers to the parent Asset.
        * component_name, the component which will contain the node result.

    '''
    print("aroma_debug: create_component")
    # Import inline to avoid issue where platform.system() is called in
    # requests __init__.py.
    import ftrack_api

    session = ftrack_api.Session()

    # Get the current node.
    node = nuke.thisNode()

    asset_id = node.node('OUT')['asset_version_id'].value()
    version = session.get('AssetVersion', asset_id)

    # Create the component and copy data to the most likely store
    component = node.node('OUT')['component_name'].value()
    out = node.node('OUT')['file'].value()

    prefix = out.split('.')[0] + '.'
    ext = os.path.splitext(out)[-1]
    start_frame = int(node.node('OUT')['first'].value())
    end_frame = int(node.node('OUT')['last'].value())

    collection = Collection(
        head=prefix,
        tail=ext,
        padding=len(str(end_frame)),
        indexes=set(range(start_frame, end_frame + 1))
    )

    version.create_component(
        str(collection), data={'name':component}, location='auto'
    )

    create_script(node, start_frame, end_frame)
    
    session.commit()
    

class ProxyPlugin(ftrack_connect_nuke_studio.processor.ProcessorPlugin):
    '''Generate proxies.'''

    def __init__(self, session, *args, **kwargs):
        '''Initialise processor.'''
        super(ProxyPlugin, self).__init__(
            *args, **kwargs
        )

        print("aroma_debug: Initialise processor.")

        self.session = session

        self.name = 'processor.proxy'
        self.defaults = {
            'OUT': {
                'file_type': 'png',
                'afterRender': (
                    'import sys;'
                    'sys.path.append("{path}");'
                    'import ftrack_processor_plugin;'
                ).format(path=self.escape_file_path(FILE_PATH))
            },
            'REFORMAT': {
                'type': 'to box',
                'scale': 0.5
            }
        }
        self.script = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), 'script.nk'
            )
        )

        
    def prepare_data(self, data):
        '''Return data mapping processed from input *data*.'''
        data = super(ProxyPlugin, self).prepare_data(data)
        print("aroma_debug: prepare_data")
        # Define output file sequence.
        format = '.####.{0}'.format(data['OUT']['file_type'])
        name = self.name.replace('.', '_')
        temporary_path = tempfile.NamedTemporaryFile(
            prefix=name, suffix=format, delete=False
        )
        #data['OUT']['file'] = temporary_path.name.replace('\\', '/')
        
        data['OUT']['file'] = "C:/tmp/"

        return data

    def discover(self, event):
        '''Return discover data for *event*.'''
        print("aroma_debug: discover")
        return {
            'defaults': self.defaults,
            'name': 'AROMA',
            'processor_name': self.name,
            'asset_name': 'BG'
        }

    def launch(self, event):
        '''Launch processor from *event*.'''
        input = event['data'].get('input', {})
        self.process(input)

    def register(self):
        '''Register processor'''
        print("aroma_debug: plugin register")
        self.session.event_hub.subscribe(
            'topic=ftrack.processor.discover and '
            'data.object_type=shot',
            self.discover
        )
        self.session.event_hub.subscribe(
            'topic=ftrack.processor.launch and data.name={0}'.format(
                self.name
            ),
            self.launch
        )

def register(session, **kw):
    '''Register plugin. Called when used as an plugin.'''
    print("aroma_debug: register")
    # Import inline to avoid issue where platform.system() is called in
    # requests __init__.py.
    import ftrack_api

    # Validate that session is an instance of ftrack_api.Session. If not,
    # assume that register is being called from an old or incompatible API and
    # return without doing anything.
    if not isinstance(session, ftrack_api.session.Session):
        return

    plugin = ProxyPlugin(
        session
    )

    plugin.register()

