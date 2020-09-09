import adsk.core
import adsk.fusion


def distToPoint(fromPoint: adsk.core.Point3D, toPoint: adsk.core.Point3D):
    return fromPoint.distanceTo(toPoint)


ORIGIN = adsk.core.Point3D.create(0, 0, 0)


def distToOrigin(fromPoint: adsk.core.Point3D) -> float:
    return distToPoint(fromPoint, ORIGIN)


def sketchLineLength(line: adsk.fusion.SketchLine) -> float:
    return line.geometry.startPoint.distanceTo(line.geometry.endPoint)


def edgeDirection(edge: adsk.fusion.BRepEdge) -> adsk.core.Vector3D:
    return edge.geometry.asInfiniteLine().direction


def arePlanesCoplanar(f1: adsk.fusion.BRepFace, f2: adsk.fusion.BRepFace) -> bool:
    return f1.geometry.isCoPlanarTo(f2.geometry)


def arePlanesParallel(f1: adsk.fusion.BRepFace, f2: adsk.fusion.BRepFace) -> bool:
    return f1.geometry.isParallelToPlane(f2.geometry)


def distBetweenFaces(f1: adsk.fusion.BRepFace, f2: adsk.fusion.BRepFace) -> float:
    normal = faceNormal(f1)
    line = adsk.core.InfiniteLine3D.create(ORIGIN, normal)

    rl1 = f1.geometry.intersectWithLine(line)
    rl2 = f2.geometry.intersectWithLine(line)

    if rl1 is None:
        raise Exception("f1 doesn't have an intersection?")
    if rl2 is None:
        raise Exception("f2 doesn't have an intersection?")

    correctReversedNormal = -1 if f1.isParamReversed else 1

    # compute the distance vector between the two intersection points,
    # and correct the sign if they're going the opposite direction of the normal
    return rl1.vectorTo(rl2).dotProduct(normal) * correctReversedNormal


def faceNormal(f1: adsk.fusion.BRepFace) -> adsk.core.Vector3D:
    return f1.geometry.normal


def edgeDirectionForComparison(edge):
    direction = edgeDirection(edge)
    if direction.x < 0:
        direction.scaleBy(-1)
    # round to a low enough precision for comparision
    return (round(direction.x, 8), round(direction.y, 8))


def lerp(p1: adsk.core.Point3D, p2: adsk.core.Point3D, amt: float) -> adsk.core.Point3D:
    amt = max(min(amt, 1), 0)
    tma = 1 - amt
    return adsk.core.Point3D.create(
        (p1.x * amt) + (p2.x * tma),
        (p1.y * amt) + (p2.y * tma),
        (p1.z * amt) + (p2.z * tma)
    )


def adskList(collection, klass):
    ret = []
    for i in range(collection.count):
        item = collection.item(i)
        casted = klass.cast(item)
        if casted is None:
            raise Exception(
                "item {} at {} was None for {}".format(item, i, klass))
        ret.append(casted)
    return ret
