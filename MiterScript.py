# Author-dymk
# Description-Create various joints

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import logging
import sys
import itertools
from . import ids
from .boundary import boundary

EPS = 0.00001

handlers = []


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
    def __init__(self, createHandler):
        # self._body1: adsk.fusion.BRepBody = None
        # self._body2: adsk.fusion.BRepBody = None
        self._createHandler = createHandler

    @boundary("onCreate")
    def onCreate(self, args: adsk.core.CommandCreatedEventArgs):
        command = args.command
        inputs = command.commandInputs

        self._bodies: List[adsk.fusion.BRepBody] = []
        self._inputs: List[adsk.core.SelectionCommandInput] = []

        self._inputs.append(inputs.addSelectionInput(
            ids.BODY1_SELECT, 'Bodies',
            'Select bodies to generate tabs between'
        ))

        for _input in self._inputs:
            _input.addSelectionFilter('SolidBodies')
            _input.setSelectionLimits(2, 0)

        command.inputChanged.add(self._createHandler(
            adsk.core.InputChangedEventHandler,
            self.onChange,
            "onChange"
        ))

        command.validateInputs.add(self._createHandler(
            adsk.core.ValidateInputsEventHandler,
            self.onValidate,
            "onValidate"
        ))

        command.execute.add(self._createHandler(
            adsk.core.CommandEventHandler,
            self.onExecute,
            "onExecute"
        ))

    @boundary("onChange")
    def onChange(self, args: adsk.core.InputChangedEventArgs):
        input_ = adsk.core.SelectionCommandInput.cast(args.input)
        if input_.id == ids.BODY1_SELECT:
            entities = [
                input_.selection(idx).entity
                for idx in range(input_.selectionCount)
            ]
            self._bodies = entities
            print("{} bodies selected".format(len(entities)))

        # find input that has focus, move to the next input
        # hasFocusIndex = next(i for i, e in enumerate(
        #     self._inputs) if e.hasFocus)
        # hasFocusIndex = (hasFocusIndex + 1) % len(self._inputs)
        # self._inputs[hasFocusIndex].hasFocus = True

    @boundary("onValidate")
    def onValidate(self, args: adsk.core.ValidateInputsEventArgs):
        # if self._body1 is None:
        #     return False
        # if self._body2 is None:
        #     return False
        return len(self._bodies) >= 2

    def app(self):
        return adsk.core.Application.get()

    def design(self):
        return adsk.fusion.Design.cast(self.app().activeProduct)

    def rootComponent(self):
        return self.design().rootComponent

    @boundary("onExecute")
    def onExecute(self, args: adsk.core.CommandEventArgs):

        pairsOfBodies = [
            (a.faces, b.faces)
            for (a, b)
            in itertools.combinations(self._bodies, 2)
        ]
        print("{} combinations of bodies".format(len(pairsOfBodies)))

        candidatePairs = list(itertools.chain(*[
            self.getCandidateFacePairs(a, b)
            for (a, b)
            in pairsOfBodies
        ]))

        drawPointsAt = []
        for pair in candidatePairs:
            print("pairing: {}, {}".format(pair[0].tempId, pair[1].tempId))
            c1 = pair[0].centroid
            c2 = pair[1].centroid
            drawPointsAt.extend(c1.asArray() + c2.asArray())

        graphics = self.rootComponent().customGraphicsGroups.add()
        graphics.addPointSet(
            adsk.fusion.CustomGraphicsCoordinates.create(
                drawPointsAt
            ),
            [i for i in range(int(len(drawPointsAt) / 3))],
            adsk.fusion.CustomGraphicsPointTypes.UserDefinedCustomGraphicsPointType,
            'res/SmallPoint.png'
        )
        self.app().activeViewport.refresh()

        existingGroups = [
            self.design().timeline.timelineGroups.item(i)
            for i in range(self.design().timeline.timelineGroups.count)
        ]
        for g in existingGroups:
            if g.name == ids.TAB_TIMELINE_GROUP:
                g.deleteMe(True)

        tlstart = self.design().timeline.markerPosition
        for pair in candidatePairs:
            self.extrudeTabs(pair)
        tlend = self.design().timeline.markerPosition-1

        if (tlend - tlstart) > 0:
            group = self.design().timeline.timelineGroups.add(tlstart, tlend)
            group.name = ids.TAB_TIMELINE_GROUP

        print("brk")

    def extrudeTabs(self, facePair: (adsk.fusion.BRepFace, adsk.fusion.BRepFace)):
        (fromFace, toFace) = facePair
        prettyName = "{} -> {}".format(fromFace.body.name, toFace.body.name)

        ac = fromFace.assemblyContext
        if ac:
            component = ac.component
        else:
            component = self.rootComponent()
        component = adsk.fusion.Component.cast(component)
        print("extruding in component {} ({})".format(
            component.name, prettyName))

        sketch = component.sketches.addWithoutEdges(fromFace)
        sketch.name = ids.TAB_SKETCH_PREFIX + prettyName
        sketch.isComputeDeferred = True

        fromFacePoints = [
            sketch.modelToSketchSpace(fromFace.vertices.item(idx).geometry)
            for idx in range(fromFace.vertices.count)
        ]

        toFacePoints = [
            sketch.modelToSketchSpace(toFace.vertices.item(idx).geometry)
            for idx in range(toFace.vertices.count)
        ]

        minToX = min([p.x for p in toFacePoints])
        maxToX = max([p.x for p in toFacePoints])
        minToY = min([p.y for p in toFacePoints])
        maxToY = max([p.y for p in toFacePoints])

        allWithin = True
        for p in fromFacePoints:
            if (p.x < minToX) or (p.x > maxToX) or (p.y < minToY) or (p.y > maxToY):
                print("({}, {}) does not lie within ({}, {}) -> ({}, {})".format(
                    *[round(i, 2) for i in [p.x, p.y, minToX, minToY, maxToX, maxToY]]
                ))
                allWithin = False

        if not allWithin:
            print("{} is not within, bailing".format(prettyName))
            sketch.deleteMe()
            return

        sketch.isComputeDeferred = False

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
    miterCommand = MiterCommand(createHandler)
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
