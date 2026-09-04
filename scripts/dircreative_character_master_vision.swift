import AppKit
import Foundation
import Vision

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write(Data("usage: vision-helper <image>\n".utf8))
    exit(2)
}

let imageURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard
    let image = NSImage(contentsOf: imageURL),
    let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil)
else {
    FileHandle.standardError.write(Data("image_unreadable\n".utf8))
    exit(2)
}

let bodyRequest = VNDetectHumanBodyPoseRequest()
let faceRequest = VNDetectFaceRectanglesRequest()
let humanRequest = VNDetectHumanRectanglesRequest()
humanRequest.upperBodyOnly = false
do {
    try VNImageRequestHandler(cgImage: cgImage).perform([bodyRequest, faceRequest, humanRequest])
} catch {
    FileHandle.standardError.write(Data("vision_request_failed\n".utf8))
    exit(2)
}

var fullBodies: [[String: Any]] = []
let humanRectangles = humanRequest.results ?? []
var usedHumanRectangleIndices = Set<Int>()
for observation in bodyRequest.results ?? [] {
    guard let points = try? observation.recognizedPoints(.all) else { continue }
    let required: [VNHumanBodyPoseObservation.JointName] = [
        .neck, .leftShoulder, .rightShoulder, .leftHip, .rightHip, .leftAnkle, .rightAnkle,
    ]
    let confident = required.compactMap { points[$0] }.filter { $0.confidence >= 0.25 }
    let visible = points.values.filter { $0.confidence >= 0.25 }
    guard confident.count == required.count, visible.count >= 8 else { continue }
    let xs = visible.map { Double($0.location.x) }
    let ys = visible.map { Double($0.location.y) }
    guard
        let minX = xs.min(), let maxX = xs.max(),
        let minY = ys.min(), let maxY = ys.max(),
        maxY - minY >= 0.50
    else { continue }
    let centerX = (minX + maxX) / 2.0
    let matchingRect = humanRectangles.enumerated()
        .filter {
            !usedHumanRectangleIndices.contains($0.offset)
                && Double($0.element.boundingBox.minX) <= centerX
                && centerX <= Double($0.element.boundingBox.maxX)
        }
        .min {
            abs(Double($0.element.boundingBox.midX) - centerX)
                < abs(Double($1.element.boundingBox.midX) - centerX)
        }
    guard let matched = matchingRect else { continue }
    usedHumanRectangleIndices.insert(matched.offset)
    let subjectRect = matched.element.boundingBox
    guard
        let leftShoulder = points[.leftShoulder],
        let rightShoulder = points[.rightShoulder]
    else { continue }
    let highestShoulderY = max(
        Double(leftShoulder.location.y),
        Double(rightShoulder.location.y)
    )
    let visibleWristCount = [
        VNHumanBodyPoseObservation.JointName.leftWrist,
        VNHumanBodyPoseObservation.JointName.rightWrist,
    ].compactMap { points[$0] }.filter { $0.confidence >= 0.25 }.count
    let visibleElbowCount = [
        VNHumanBodyPoseObservation.JointName.leftElbow,
        VNHumanBodyPoseObservation.JointName.rightElbow,
    ].compactMap { points[$0] }.filter { $0.confidence >= 0.25 }.count
    fullBodies.append([
        "center_x": centerX,
        "min_y": minY,
        "max_y": maxY,
        "joint_span": maxY - minY,
        "subject_height": Double(subjectRect.height),
        "head_extent_above_shoulders": Double(subjectRect.maxY) - highestShoulderY,
        "subject_top_clearance": 1.0 - Double(subjectRect.maxY),
        "subject_bottom_clearance": Double(subjectRect.minY),
        "visible_wrist_count": visibleWristCount,
        "visible_elbow_count": visibleElbowCount,
        "visible_upper_limb_joint_count": visibleWristCount + visibleElbowCount,
        "human_rect_index": matched.offset,
        "human_rect_min_x": Double(subjectRect.minX),
        "human_rect_max_x": Double(subjectRect.maxX),
    ])
}
fullBodies.sort { ($0["center_x"] as? Double ?? 0) < ($1["center_x"] as? Double ?? 0) }

var closeupFaces: [[String: Any]] = []
var allFaces: [[String: Any]] = []
for observation in faceRequest.results ?? [] {
    let box = observation.boundingBox
    allFaces.append([
        "center_x": Double(box.midX),
        "center_y": Double(box.midY),
        "width": Double(box.width),
        "height": Double(box.height),
    ])
    if box.midX <= 0.30 && box.width >= 0.10 && box.height >= 0.16 {
        closeupFaces.append([
            "center_x": Double(box.midX),
            "center_y": Double(box.midY),
            "width": Double(box.width),
            "height": Double(box.height),
        ])
    }
}

let result: [String: Any] = [
    "backend": "apple-vision-human-body-pose-v1",
    "image_width": cgImage.width,
    "image_height": cgImage.height,
    "body_pose_count": bodyRequest.results?.count ?? 0,
    "face_count": faceRequest.results?.count ?? 0,
    "faces": allFaces,
    "human_rectangle_count": humanRequest.results?.count ?? 0,
    "full_body_count": fullBodies.count,
    "full_bodies": fullBodies,
    "left_closeup_face_count": closeupFaces.count,
    "left_closeup_faces": closeupFaces,
]
let encoded = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
FileHandle.standardOutput.write(encoded)
FileHandle.standardOutput.write(Data("\n".utf8))
