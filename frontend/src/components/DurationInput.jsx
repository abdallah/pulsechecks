/**
 * DurationInput - A number input with a unit selector (minutes/hours/days).
 * Displays a human-friendly unit while storing/emitting values in seconds.
 *
 * Props:
 *   value       - current value in seconds
 *   onChange    - called with new value in seconds
 *   id          - input element id (for label htmlFor)
 *   min         - minimum value in seconds (default 0)
 *   required    - whether the input is required
 *   className   - additional class names for the wrapper div
 */
import { useState, useEffect } from 'react'

function bestUnit(seconds) {
  if (seconds >= 86400 && seconds % 86400 === 0) return 'days'
  if (seconds >= 3600 && seconds % 3600 === 0) return 'hours'
  return 'minutes'
}

const MULTIPLIERS = { minutes: 60, hours: 3600, days: 86400 }

export default function DurationInput({ value, onChange, id, min = 0, required = false, className = '' }) {
  const [unit, setUnit] = useState(() => bestUnit(value))
  const [displayValue, setDisplayValue] = useState(() => Math.round(value / MULTIPLIERS[bestUnit(value)]))

  // Sync display when value changes externally (e.g. form reset)
  useEffect(() => {
    const u = bestUnit(value)
    setUnit(u)
    setDisplayValue(Math.round(value / MULTIPLIERS[u]))
  }, [value])

  function handleValueChange(e) {
    const num = parseInt(e.target.value) || 0
    setDisplayValue(num)
    onChange(num * MULTIPLIERS[unit])
  }

  function handleUnitChange(e) {
    const newUnit = e.target.value
    // Keep the seconds value, just re-display in new unit
    const newDisplay = Math.round(value / MULTIPLIERS[newUnit])
    setUnit(newUnit)
    setDisplayValue(newDisplay || 1)
  }

  return (
    <div className={`flex gap-2 ${className}`}>
      <input
        type="number"
        id={id}
        value={displayValue}
        onChange={handleValueChange}
        className="block flex-1 min-w-0 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
        min={Math.max(1, Math.ceil(min / MULTIPLIERS[unit]))}
        required={required}
      />
      <select
        value={unit}
        onChange={handleUnitChange}
        className="block w-20 border border-gray-300 rounded-md shadow-sm py-2 px-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm bg-white"
        aria-label="Time unit"
      >
        <option value="minutes">min</option>
        <option value="hours">hrs</option>
        <option value="days">days</option>
      </select>
    </div>
  )
}
