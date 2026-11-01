// Shared by the admin cards. Missing data is shown as text, never as 0 or a guess.
export const NO_DATA = 'Not enough data'
export const percent = value => (value == null ? NO_DATA : `${value}%`)
export const money = value => (value == null ? NO_DATA : `$${Math.round(value).toLocaleString('en-US')}`)
export const growth = value => (value == null ? NO_DATA : `${value > 0 ? '+' : ''}${value}%`)
