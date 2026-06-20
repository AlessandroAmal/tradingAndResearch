import { useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'

// Candlestick chart from ascending [{ts, open, high, low, close}] rows.
export default function PriceChart({ bars }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      height: 320,
      layout: { background: { color: 'transparent' }, textColor: '#cbd5e1' },
      grid: {
        vertLines: { color: 'rgba(148,163,184,0.1)' },
        horzLines: { color: 'rgba(148,163,184,0.1)' },
      },
      rightPriceScale: { borderColor: 'rgba(148,163,184,0.2)' },
      timeScale: { borderColor: 'rgba(148,163,184,0.2)' },
      autoSize: true,
    })
    chartRef.current = chart
    seriesRef.current = chart.addCandlestickSeries({
      upColor: '#22c55e', downColor: '#ef4444',
      borderVisible: false, wickUpColor: '#22c55e', wickDownColor: '#ef4444',
    })
    const handle = () => chart.timeScale().fitContent()
    window.addEventListener('resize', handle)
    return () => {
      window.removeEventListener('resize', handle)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !bars) return
    const data = bars
      .filter((b) => b.close != null)
      .map((b) => ({
        time: Math.floor(new Date(b.ts).getTime() / 1000),
        open: b.open, high: b.high, low: b.low, close: b.close,
      }))
    seriesRef.current.setData(data)
    chartRef.current?.timeScale().fitContent()
  }, [bars])

  return <div ref={containerRef} className="chart" />
}
