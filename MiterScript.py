# Author-dymk
# Description-Create various joints

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import logging
import sys
from . import ids

EPS = 0.00001
handlers = []


def boundary(name):
    def _withName(func):
        def _withTryExcept(*args):
            try:
                return func(*args)
            except:
                print("error in {}:\n{}".format(name, traceback.format_exc()))
                return None
        return _withTryExcept
    return _withName


def createHandler(klass, method, name):
    class _Handler(klass):
        def __init__(self):
            super().__init__()
            print("initialized {} handler".format(name))

        def notify(self, arg):
            print("handler {} called".format(name))
            method(arg)

    handler = _Handler()
    handlers.append(handler)
    return handler


class MiterCommand():
    def __init__(self):
        self._body1: adsk.fusion.BRepBody = None
        self._body2: adsk.fusion.BRepBody = None
        self._inputs: List[adsk.core.SelectionCommandInput] = []

    def onCreate(self, args: adsk.core.CommandCreatedEventArgs):
        app = adsk.core.Application.get()
        ui = app.userInterface
        try:
            command = args.command
            inputs = command.commandInputs

            self._inputs.append(inputs.addSelectionInput(
                ids.BODY1_SELECT, 'Body 1',
                'Select a body to make slots into '
            ))

            self._inputs.append(inputs.addSelectionInput(
                ids.BODY2_SELECT, 'Body 2',
                'Select an adjacent body'
            ))

            for _input in self._inputs:
                _input.addSelectionFilter('SolidBodies')
                _input.setSelectionLimits(1, 1)

            command.inputChanged.add(createHandler(
                adsk.core.InputChangedEventHandler,
                self.onChange,
                "onChange"
            ))

            command.validateInputs.add(createHandler(
                adsk.core.ValidateInputsEventHandler,
                self.onValidate,
                "onValidate"
            ))

            command.execute.add(createHandler(
                adsk.core.CommandEventHandler,
                self.onExecute,
                "onExecute"
            ))

        except:
            print("error: {}".format(traceback.format_exc()))

    @boundary("onChange")
    def onChange(self, args: adsk.core.InputChangedEventArgs):
        input_ = adsk.core.SelectionCommandInput.cast(args.input)
        if input_.selectionCount != 1:
            print("input {} has non-1 selection count: {}".format(
                input_.id, input_.selectionCount
            ))
            return

        entity = adsk.fusion.BRepBody.cast(input_.selection(0).entity)
        if input_.id == ids.BODY1_SELECT:
            self._body1 = entity
        if input_.id == ids.BODY2_SELECT:
            self._body2 = entity

        # find input that has focus, move to the next input
        hasFocusIndex = next(i for i, e in enumerate(
            self._inputs) if e.hasFocus)
        hasFocusIndex = (hasFocusIndex + 1) % len(self._inputs)
        self._inputs[hasFocusIndex].hasFocus = True

        print("body {} selected for input {}".format(entity.name, input_.id))

    @boundary("onValidate")
    def onValidate(self, args: adsk.core.ValidateInputsEventArgs):
        if self._body1 is None:
            return False
        if self._body2 is None:
            return False
        return True

    @boundary("onExecute")
    def onExecute(self, args: adsk.core.CommandEventArgs):
        b1faces = self._body1.faces
        b2faces = self._body2.faces

        drawPointsAt = []
        candidatePairs = self.getCandidateFacePairs(b1faces, b2faces)

        for pair in candidatePairs:
            print("pairing: {}, {}".format(pair[0].tempId, pair[1].tempId))
            c1 = pair[0].centroid
            c2 = pair[1].centroid
            drawPointsAt.extend(c1.asArray() + c2.asArray())

        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent
        graphics = root.customGraphicsGroups.add()
        graphics.addPointSet(
            adsk.fusion.CustomGraphicsCoordinates.create(
                drawPointsAt
            ),
            [i for i in range(int(len(drawPointsAt) / 3))],
            adsk.fusion.CustomGraphicsPointTypes.UserDefinedCustomGraphicsPointType,
            'res/SmallPoint.png'
        )
        app.activeViewport.refresh()
        print("brk")

    def getCandidateFacePairs(
        self,
        faces1: adsk.fusion.BRepFace,
        faces2: adsk.fusion.BRepFace
    ) -> (adsk.fusion.BRepFace, adsk.fusion.BRepFace):
        def isCoplanar(f1, f2):
            return f1.geometry.isCoPlanarTo(f2.geometry)

        def doFaceEachOther(f1, f2):
            # if n1+n2 == 0, they're complementary vectors
            v1 = f1.geometry.normal.copy()
            v2 = f2.geometry.normal.copy()

            if f1.isParamReversed:
                v1.scaleBy(-1)
            if f2.isParamReversed:
                v2.scaleBy(-1)

            v1.add(v2)
            return v1.length < EPS

        # [0] - the smaller brep face (gets notches extruded from)
        # [1] - the larger brep face (gets cut into)
        candidatePairs: (adsk.fusion.BRepFace, adsk.fusion.BRepFace) = []
        for f1 in faces1:
            for f2 in faces2:
                coplanar = isCoplanar(f1, f2)
                if coplanar:
                    print("these planes are coplanar:    {}, {}".format(
                        f1.tempId, f2.tempId))
                faceEachOther = doFaceEachOther(f1, f2)
                if faceEachOther:
                    print("these planes face each other: {}, {}".format(
                        f1.tempId, f2.tempId))

                if coplanar and faceEachOther:
                    candidatePairs.append(
                        (f1, f2) if f1.area < f2.area else (f2, f1)
                    )

        return candidatePairs


def v3d(p: adsk.core.Vector3D) -> (float, float, float):
    return (p.x, p.y, p.z)


def tryRemove():
    app = adsk.core.Application.get()
    ui = app.userInterface
    cmdDef = ui.commandDefinitions.itemById(ids.MAIN_BUTTON_ID)
    if cmdDef:
        cmdDef.deleteMe()
    createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')
    cntrl = createPanel.controls.itemById(ids.MAIN_BUTTON_ID)
    if cntrl:
        cntrl.deleteMe()

    root = adsk.fusion.Design.cast(app.activeProduct).rootComponent

    if root.customGraphicsGroups.count > 0:
        root.customGraphicsGroups.item(0).deleteMe()
        app.activeViewport.refresh()

    print("removed def: {}".format(
        cmdDef is not None))
    print("removed ctrl: {}".format(
        cntrl is not None))


@boundary("run")
def run(context):
    tryRemove()
    app = adsk.core.Application.get()
    ui = app.userInterface
    miterCommand = MiterCommand()
    handlers.append(miterCommand)

    button = ui.commandDefinitions.addButtonDefinition(
        ids.MAIN_BUTTON_ID,
        'Miter',
        'Miters everything',
        'res'
    )

    button.commandCreated.add(createHandler(
        adsk.core.CommandCreatedEventHandler,
        miterCommand.onCreate,
        "onCreate"
    ))

    createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')
    buttonControl = createPanel.controls.addCommand(
        button,
        ids.MAIN_BUTTON_ID
    )

    # Make the button available in the panel.
    buttonControl.isPromotedByDefault = True
    buttonControl.isPromoted = True
    print("started addin")


@boundary("stop")
def stop(context):
    tryRemove()
    print("stopped addin")
