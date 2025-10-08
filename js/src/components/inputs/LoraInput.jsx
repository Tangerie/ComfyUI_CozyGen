import React from 'react';

const LoraInput = ({ value, onChange, choices }) => {
  return (
    <div className="w-full flex flex-row">
      <select
        className="w-1/2 block p-2.5 border border-base-300 bg-base-100 text-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent transition-all disabled:bg-base-300/50 disabled:cursor-not-allowed disabled:text-gray-400"
        value={value.lora || 'None'}
        onChange={(e) => onChange({ ...value, lora: e.target.value })}
      >
        {Array.isArray(choices) && choices.map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
      </select>
      <input
        type="number"
        className="block w-1/2 p-2.5 border border-base-300 bg-base-100 text-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent transition-all disabled:bg-base-300/50 disabled:cursor-not-allowed disabled:text-gray-400"
        value={value.strength || 0}
        onChange={(e) => onChange({ ...value, strength: parseFloat(e.target.value) })}
        min={-5}
        max={5}
        step={0.01}
      />
    </div>
  );
};

export default LoraInput;
