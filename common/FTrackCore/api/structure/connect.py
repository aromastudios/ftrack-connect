# :coding: utf-8
# :copyright: Copyright (c) 2014 ftrack

from .base import Structure
from ..component import Component
from ..client import Asset, AssetVersion


class ConnectStructure(Structure):
    '''Connect structure supporting directory generation for connect.'''

    def _getCommonStructureFragment(self, hierarchy):
        '''Return common structure fragment for *hierarchy*.

        Examine the *hierarchy* and return ordered list of names to use for
        common structure in directory path and file name.

        Example result::

            ['myproject', 'sc001', '010', 'img', 'render', 'v001']

        '''
        structure = []

        for ancestor in reversed(hierarchy):
            try:
                name = ancestor.getName()

            except AttributeError:
                if isinstance(ancestor, AssetVersion):
                    # Add padded version number for asset version.
                    version = 'v{0:03d}'.format(ancestor.getVersion())
                    structure.append(version)

                continue

            if name == 'Asset builds':
                # Special name for asset build parent.
                structure.append('assetb')

            elif isinstance(ancestor, Component):
                pass

            else:
                if isinstance(ancestor, Asset):
                    # Insert asset type short code.
                    assetType = ancestor.getType().getShort()
                    structure.append(assetType)

                structure.append(name)

        return structure

    def getResourceIdentifier(self, entity):
        '''Return a *resourceIdentifier* for supplied *entity*.

        Construct the returned *resourceIdentifier* by examining the hierarchy
        of entities for the supplied *entity* and using the names of those to
        build a corresponding directory structure hierarchy. Then append any
        existing resource identifier of *entity* to that structure.

        The following is the pattern used for the hierarchy:


            /{disk}/{projectFolder}/{assetPathPrefix}/
            {sequenceName|'assetb'}/{shotName|assetBuildName}/{assetType}/{assetName}/{versionNumber}/
            {projectName}_{sequenceName|'assetb'}_{shotName|assetBuildName}_{assetType}_{assetName}_{versionNumber}_{componentName}.{frame|range}.{extension}

        Example of a resulting resourceIdentifier for a shot render:

            /demo/test/ftrack/assets/sc010/010/img/spacestationLights/v001/
            test_sc010_010_img_spacestationLights_v001_main.%04d.exr

        Example of a resulting resourceIdentifier for an asset build:

            /demo/test/ftrack/assets/assetb/spacestation/geo/model/v001/
            test_assetb_spacestation_geo_model_v001_main.mb

        .. Note::

            The returned *resourceIdentifier* is always an absolute path.

        .. Note::

            If *entity* is a member of a container then the container will be
            used to determine the directory structure for the component. This
            ensures that all members of a container end up in the same parent
            directory structure.

        '''
        if not isinstance(entity, Component):
            raise NotImplementedError('Cannot generate path for unsupported '
                                      'entity {0}'.format(entity))

        component = entity
        container = component.getContainer(location=None)

        if container:
            # Use container for consistency across sibling members.
            # TODO: Handle non-sequence case.
            hierarchy = container.getParents()
        else:
            hierarchy = component.getParents()

        # Construct common structure fragment for directory and file names.
        commonStructureFragment = self._getCommonStructureFragment(hierarchy)

        # Construct structure.
        structure = []

        # Add project root, project-folder and asset prefix.
        # E.g. /demo/test/ftrack/assets
        project = hierarchy[-1]
        structure.append(
            project.getPath(True)
        )

        # Add intermediate structure excluding project name.
        # E.g. sc010/010/img/spacestationLights/v001/
        structure.extend(commonStructureFragment[1:])

        # Compute and add new filename if appropriate. Note that a sequence will
        # have a filename in the form prefix.%04d.ext whilst a general container
        # will have no filename.
        # E.g. test_sc010_010_img_spacestationLights_v001_main.%04d.exr
        fileNameFragment = commonStructureFragment[:]

        if container:
            # Use container name for consistency across sibling members.
            # TODO: Handle non-sequence case.
            fileNameFragment.append(container.getName())
        else:
            fileNameFragment.append(component.getName())

        fileName = '_'.join(fileNameFragment)

        if container:
            # Member of a container so add entity name as index.
            # TODO: Handle non-sequence member case.
            fileName += '.{0}'.format(entity.getName())

        elif component.isContainer():
            if component.isSequence():
                # Add a sequence identifier.
                sequenceExpression = self._getSequenceExpression(component)
                fileName += '.{0}'.format(sequenceExpression)

            else:
                # Other containers have no fileName.
                fileName = None

        if fileName is not None:
            if container:
                # Use container extension for consistency across sibling
                # members. TODO: Handle non-sequence case.
                if container.getFileType():
                    fileName += container.getFileType()
            else:
                if component.getFileType():
                    fileName += component.getFileType()

            structure.append(fileName)

        return self.pathSeparator.join(structure)
