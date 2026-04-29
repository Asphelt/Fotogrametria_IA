import Foundation
import RealityKit

guard CommandLine.arguments.count >= 3 else {
    fputs("Usage: PhotogrammetryTool <input_dir> <output_usdz>\n", stderr)
    Foundation.exit(1)
}

let inputPath  = CommandLine.arguments[1]
let outputPath = CommandLine.arguments[2]

@available(macOS 12.0, *)
func run() async {
    let inputURL  = URL(fileURLWithPath: inputPath)
    let outputURL = URL(fileURLWithPath: outputPath)

    do {
        var config = PhotogrammetrySession.Configuration()
        config.featureSensitivity = .normal
        config.isObjectMaskingEnabled = false

        let session = try PhotogrammetrySession(input: inputURL, configuration: config)

        try session.process(requests: [
            .modelFile(url: outputURL, detail: .medium)
        ])

        for try await out in session.outputs {
            switch out {
            case .requestProgress(_, let fraction):
                let pct = Int(fraction * 100)
                print("PROGRESS:\(pct)")
                fflush(stdout)
            case .requestComplete:
                print("REQUEST_COMPLETE")
                fflush(stdout)
            case .processingComplete:
                print("DONE")
                fflush(stdout)
                Foundation.exit(0)
            case .requestError(_, let error):
                fputs("ERROR:\(error.localizedDescription)\n", stderr)
                Foundation.exit(1)
            case .processingCancelled:
                fputs("CANCELLED\n", stderr)
                Foundation.exit(1)
            case .invalidSample(let id, let reason):
                fputs("INVALID_SAMPLE id=\(id) reason=\(reason)\n", stderr)
            case .skippedSample(let id):
                fputs("SKIPPED_SAMPLE id=\(id)\n", stderr)
            default:
                break
            }
        }
    } catch {
        fputs("FATAL:\(error.localizedDescription)\n", stderr)
        Foundation.exit(1)
    }
}

if #available(macOS 12.0, *) {
    let sema = DispatchSemaphore(value: 0)
    Task {
        await run()
        sema.signal()
    }
    sema.wait()
} else {
    fputs("Requires macOS 12.0+\n", stderr)
    Foundation.exit(1)
}
