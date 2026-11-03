# Prediction, written before any read

- Bars: 2 bits per form on held, on forms at 25 bits or more, makes this the next steer. Under .5 closes this form.
- Going backward from OUT saves 1 to 2.5 bits per form on the forms nearest the output and under .5 on forms more than 3 steps from it, as need moves little at depth.
- Columns of a form given the form that reads it carry most of the saving. A need fact per candidate table beats need facts per state by at least .3 bits per form.
