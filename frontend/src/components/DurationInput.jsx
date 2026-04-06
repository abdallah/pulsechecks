/**
 * DurationInput - A number input with a unit selector (minutes/hours/days).
 * Displays a human-friendly unit while storing/emitting values in seconds.
 *
 * Props:
 *   value       - initial value in seconds (used only on mount — use key prop to reset)
 *   onChange    - called with new value in seconds whenever it changes
 *   id          - input element id (for label htmlFor)
 *   min         - minimum value in seconds (default 0)
 *   required    - whether the input is required
 *   className   - additional class names for the wrapper div
 */
import { useState } from 'react'

function bestUnit(seconds) {
  if (seconds >= 86400 && seconds % 86400 === 0) return 'days'
  if (seconds >= 3600  && seconds % 3600  === 0) return 'hours'
  return 'minutes'
}

const MULTIPLIERS = { minutes: 60, hours: 3600, days: 86400 }

export default function DurationInput({ value, onChange, id, min = 0, required = false, className = '' }) {
  // Initialise from prop once — parent must change `key` to reset
  const [unit, setUnit] = useState(() => bestUnit(value))
  const [display, setDisplay] = useState(() => Math.round(value / MULTIPLIERS[bestUnit(value)]))

  function handleValueChange(e) {
    const num = parseInt(e.target.value) || 0
    setDisplay(num)
    onChange(num * MULTIPLIERS[unit])
  }

  function handleUnitChange(e) {
    const newUnit = e.target.value
    // Convert the current *display* value (not prop) to new unit
    const currentSeconds = display * MULTIPLIERS[unit]
    const newDisplay = Math.round(currentSeconds / MULTIPLIERS[newUnit]) || 1
    setUnit(newUnit)
    setDisplay(newDisplay)
    onChange(newDisplay * MULTIPLIERS[newUnit])
  }

  const minDisplay = Math.max(0, Math.ceil(min / MULTIPLIERS[unit]))

  return (
    <div className={`flex gap-2 ${className}`}>
      <input
        type="number"
        id={id}
        value={display}
        onChange={handleValueChange}
        className="block flex-1 min-w-0 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
        min={minDisplay}
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
