// MetalRenderer.swift — PlaybackKit
// CVPixelBuffer → Metal → MTKView 渲染
// 使用 Metal Texture Cache 实现零拷贝 GPU 渲染

import Metal
import MetalKit
import CoreVideo
import CoreMedia
import simd

// MARK: - Pixel Buffer Queue

/// 线程安全的帧队列（解码线程写，渲染线程读）
final class PixelBufferQueue: @unchecked Sendable {
    private var buffer: CVPixelBuffer?
    private let lock = NSLock()

    func enqueue(_ pb: CVPixelBuffer) {
        lock.withLock { buffer = pb }
    }

    func dequeue() -> CVPixelBuffer? {
        lock.withLock {
            let pb = buffer
            buffer = nil
            return pb
        }
    }
}

// MARK: - MetalRenderer

/// Metal 渲染器：将 CVPixelBuffer 渲染到 MTKView
public final class MetalRenderer: NSObject, MTKViewDelegate {

    // Metal 对象
    private let device: MTLDevice
    private let commandQueue: MTLCommandQueue
    private var pipelineState: MTLRenderPipelineState?
    private var textureCache: CVMetalTextureCache?

    // 帧队列
    private let queue = PixelBufferQueue()

    // 顶点缓冲（全屏四边形）
    private var vertexBuffer: MTLBuffer?

    // MARK: - Init

    override public init() {
        guard let device = MTLCreateSystemDefaultDevice(),
              let queue = device.makeCommandQueue() else {
            fatalError("Metal is not available on this device")
        }
        self.device = device
        self.commandQueue = queue
        super.init()

        setupPipeline()
        setupTextureCache()
        setupVertexBuffer()
    }

    // MARK: - Public API

    /// 将 CVPixelBuffer 送入渲染队列
    public func enqueue(pixelBuffer: CVPixelBuffer, pts: CMTime) {
        queue.enqueue(pixelBuffer)
    }

    /// 配置 MTKView（在 View 创建后调用一次）
    public func configure(view: MTKView) {
        view.device = device
        view.delegate = self
        view.framebufferOnly = true
        view.colorPixelFormat = .bgra8Unorm
        view.clearColor = MTLClearColor(red: 0, green: 0, blue: 0, alpha: 1)
        view.preferredFramesPerSecond = 60
        view.isPaused = false
        view.enableSetNeedsDisplay = false
    }

    // MARK: - MTKViewDelegate

    public func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {}

    public func draw(in view: MTKView) {
        guard let pixelBuffer = queue.dequeue(),
              let drawable = view.currentDrawable,
              let descriptor = view.currentRenderPassDescriptor,
              let commandBuffer = commandQueue.makeCommandBuffer(),
              let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: descriptor),
              let pipelineState = pipelineState,
              let texture = makeTexture(from: pixelBuffer) else {
            return
        }

        encoder.setRenderPipelineState(pipelineState)
        encoder.setVertexBuffer(vertexBuffer, offset: 0, index: 0)
        encoder.setFragmentTexture(texture, index: 0)
        encoder.drawPrimitives(type: .triangleStrip, vertexStart: 0, vertexCount: 4)
        encoder.endEncoding()

        commandBuffer.present(drawable)
        commandBuffer.commit()
    }

    // MARK: - Private Setup

    private func setupPipeline() {
        let library: MTLLibrary
        do {
            // 内联着色器源码（避免依赖 .metal 文件）
            library = try device.makeLibrary(source: Self.shaderSource, options: nil)
        } catch {
            print("[MetalRenderer] Failed to compile shaders: \(error)")
            return
        }

        let descriptor = MTLRenderPipelineDescriptor()
        descriptor.vertexFunction = library.makeFunction(name: "vertexShader")
        descriptor.fragmentFunction = library.makeFunction(name: "fragmentShader")
        descriptor.colorAttachments[0].pixelFormat = .bgra8Unorm

        do {
            pipelineState = try device.makeRenderPipelineState(descriptor: descriptor)
        } catch {
            print("[MetalRenderer] Failed to create pipeline state: \(error)")
        }
    }

    private func setupTextureCache() {
        CVMetalTextureCacheCreate(kCFAllocatorDefault, nil, device, nil, &textureCache)
    }

    private func setupVertexBuffer() {
        // 全屏四边形（NDC 坐标），UV 坐标需要上下翻转
        let vertices: [Float] = [
        //  x      y     u     v
           -1.0,  -1.0,  0.0,  1.0,   // 左下
            1.0,  -1.0,  1.0,  1.0,   // 右下
           -1.0,   1.0,  0.0,  0.0,   // 左上
            1.0,   1.0,  1.0,  0.0,   // 右上
        ]
        vertexBuffer = device.makeBuffer(
            bytes: vertices,
            length: vertices.count * MemoryLayout<Float>.size,
            options: .storageModeShared
        )
    }

    private func makeTexture(from pixelBuffer: CVPixelBuffer) -> MTLTexture? {
        guard let cache = textureCache else { return nil }
        let width  = CVPixelBufferGetWidth(pixelBuffer)
        let height = CVPixelBufferGetHeight(pixelBuffer)
        var cvTexture: CVMetalTexture?
        CVMetalTextureCacheCreateTextureFromImage(
            kCFAllocatorDefault, cache, pixelBuffer, nil,
            .bgra8Unorm, width, height, 0, &cvTexture
        )
        guard let cvTex = cvTexture else { return nil }
        return CVMetalTextureGetTexture(cvTex)
    }

    // MARK: - Inline Metal Shader Source

    private static let shaderSource = """
    #include <metal_stdlib>
    using namespace metal;

    struct VertexIn {
        float2 position [[attribute(0)]];
        float2 uv       [[attribute(1)]];
    };

    struct VertexOut {
        float4 position [[position]];
        float2 uv;
    };

    vertex VertexOut vertexShader(uint vid [[vertex_id]],
                                  const device float4* vertices [[buffer(0)]]) {
        VertexOut out;
        float4 v = vertices[vid];
        out.position = float4(v.x, v.y, 0.0, 1.0);
        out.uv = float2(v.z, v.w);
        return out;
    }

    fragment float4 fragmentShader(VertexOut in [[stage_in]],
                                   texture2d<float> tex [[texture(0)]]) {
        constexpr sampler s(filter::linear, address::clamp_to_edge);
        return tex.sample(s, in.uv);
    }
    """
}
