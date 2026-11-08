.global _start
.text
_start:
    mov $100000, %ecx
loop:
    sub $1, %ecx
    jne loop
    mov $60, %eax
    xor %edi, %edi
    syscall
.section .note.GNU-stack,"",@progbits
