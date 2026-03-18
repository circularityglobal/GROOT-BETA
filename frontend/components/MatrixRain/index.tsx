'use client'

import { useRef, useEffect } from 'react'

interface MatrixRainProps {
  color?: string
  opacity?: number
  density?: number
  speed?: number
  className?: string
}

export default function MatrixRain({
  color = '#5CE0D2',
  opacity = 0.08,
  density = 18,
  speed = 1,
  className = '',
}: MatrixRainProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // Respect prefers-reduced-motion
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (mq.matches) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let columns: number[] = []
    const chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789GROOTREFI0x'

    function resize() {
      const dpr = window.devicePixelRatio || 1
      canvas!.width = canvas!.offsetWidth * dpr
      canvas!.height = canvas!.offsetHeight * dpr
      ctx!.scale(dpr, dpr)
      const colCount = Math.floor(canvas!.offsetWidth / density)
      columns = Array(colCount).fill(0).map(() => Math.random() * canvas!.offsetHeight / density)
    }

    resize()

    function draw() {
      ctx!.fillStyle = `rgba(5, 5, 5, 0.12)`
      ctx!.fillRect(0, 0, canvas!.offsetWidth, canvas!.offsetHeight)

      ctx!.fillStyle = color
      ctx!.font = `${density - 4}px 'JetBrains Mono', monospace`

      for (let i = 0; i < columns.length; i++) {
        const char = chars[Math.floor(Math.random() * chars.length)]
        const x = i * density
        const y = columns[i] * density

        ctx!.globalAlpha = 0.4 + Math.random() * 0.6
        ctx!.fillText(char, x, y)

        if (y > canvas!.offsetHeight && Math.random() > 0.975) {
          columns[i] = 0
        }
        columns[i] += speed * (0.5 + Math.random() * 0.5)
      }

      ctx!.globalAlpha = 1
      animId = requestAnimationFrame(draw)
    }

    animId = requestAnimationFrame(draw)

    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [color, density, speed])

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 w-full h-full pointer-events-none ${className}`}
      style={{ opacity }}
    />
  )
}
