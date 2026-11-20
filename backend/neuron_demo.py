
# MyAI - Simple Neural Network Neuron

def neuron(x1, x2):

    # Weights
    w1 = 0.5
    w2 = 0.2

    # Bias
    bias = 1

    # Weighted sum
    z = (x1 * w1) + (x2 * w2) + bias

    # ReLU activation
    output = max(0, z)

    return output


# Input values
input1 = 5
input2 = 6

result = neuron(input1, input2)

print("Input 1:", input1)
print("Input 2:", input2)
print("Neuron output:", result)
